"""OpenAI integration and JSON result parsing."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from statistics import mean

from config import BW_FOCUS_SUBJECTS, BW_FOCUS_TOPICS, JSON_SCHEMA_HINT, MODEL_FALLBACKS, RESULT_JSON_SCHEMA, SYSTEM_PROMPT
from models.app_settings import AppSettings
from models.task_result import TaskResult
from services.cost_service import UsageEstimate, build_usage_estimate
from services.screenshot_service import ScreenshotService
from services.task_detector import TaskDetector
from utils.validation import looks_like_api_key, safe_json_loads

LOGGER = logging.getLogger(__name__)


class OpenAIServiceError(RuntimeError):
    pass


class OpenAIService:
    provider_name = "openai"

    def __init__(self, settings: AppSettings, detector: TaskDetector) -> None:
        self.settings = settings
        self.detector = detector
        self._client = None
        self._client_lock = threading.Lock()
        self.last_model_notice = ""

    def update_settings(self, settings: AppSettings) -> None:
        old_key = self._api_key()
        old_model = self._model()
        old_timeout = self.settings.timeout_seconds
        self.settings = settings
        if self._api_key() != old_key or self._model() != old_model or settings.timeout_seconds != old_timeout:
            self._client = None

    def analyze_task(
        self,
        input_text: str = "",
        image_path: Path | None = None,
        settings: AppSettings | None = None,
        forced_mode: str = "auto",
    ) -> TaskResult:
        if settings is not None and settings is not self.settings:
            self.update_settings(settings)
        if image_path is not None:
            return self.analyze_image(image_path, forced_mode)
        return self.analyze_text(input_text, forced_mode)

    def analyze_text(self, text: str, forced_mode: str = "auto") -> TaskResult:
        if not text.strip():
            return TaskResult(
                task_type="no_task",
                short_answer="nichts erkannt",
                full_answer="Es wurde kein Text eingegeben.",
                confidence=1.0,
                source="text",
            )
        hint = self.detector.quick_detect(text) if forced_mode == "auto" and self.settings.auto_detect_tasks else forced_mode
        if hint == "auto" and not self.settings.auto_detect_tasks:
            hint = "generic_text"
        exam_context = self.detector.detect_exam_context(text)
        prompt = self._build_prompt(source_type="text", mode_hint=hint, text=text, exam_context=exam_context)
        raw, usage = self._send(prompt, image_data_url=None)
        result = self._parse_result(raw, "text")
        self._apply_usage(result, usage)
        self._apply_service_warnings(result)
        if exam_context and self.settings.enable_learning_guardrails:
            result.confidence = min(result.confidence, 0.45)
            if not any("Pruefung" in warning or "Test" in warning for warning in result.warnings):
                result.warnings.append("Moeglicher Pruefungs-/Testkontext erkannt: Nutze die Antwort nur zum Lernen.")
        return result

    def analyze_image(self, image_path: Path, forced_mode: str = "auto") -> TaskResult:
        b64 = ScreenshotService.encode_base64(image_path)
        data_url = f"data:image/png;base64,{b64}"
        hint = forced_mode if forced_mode != "auto" else ("auto" if self.settings.auto_detect_tasks else "generic_text")
        prompt = self._build_prompt(source_type="screenshot", mode_hint=hint, text="", exam_context=False)
        raw, usage = self._send(prompt, image_data_url=data_url)
        result = self._parse_result(raw, "screenshot")
        self._apply_usage(result, usage)
        self._apply_service_warnings(result)
        return result

    def _get_client(self):
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            if not looks_like_api_key(self._api_key()):
                raise OpenAIServiceError("OpenAI API-Key fehlt. Bitte in Settings oder .env eintragen.")
            try:
                from openai import OpenAI
            except Exception as exc:
                raise OpenAIServiceError("OpenAI-Paket fehlt. Installiere die requirements.txt.") from exc
            try:
                self._client = OpenAI(api_key=self._api_key(), timeout=self.settings.timeout_seconds)
            except TypeError:
                self._client = OpenAI(api_key=self._api_key())
            return self._client

    def _send(self, prompt: str, image_data_url: str | None) -> tuple[str, UsageEstimate]:
        client = self._get_client()
        self.last_model_notice = ""
        errors: list[str] = []
        candidates = self._candidate_models()
        for index, model in enumerate(candidates, start=1):
            try:
                fallback_used = index > 1
                if hasattr(client, "responses"):
                    try:
                        return self._send_responses(client, prompt, image_data_url, model, fallback_used)
                    except TypeError:
                        LOGGER.info("Responses call shape unsupported, falling back to chat completions", exc_info=True)
                return self._send_chat(client, prompt, image_data_url, model, fallback_used)
            except Exception as exc:
                friendly = self._friendly_api_error(exc)
                errors.append(f"{model}: {friendly}")
                if self._model_unavailable(exc) and index < len(candidates):
                    fallback = candidates[index]
                    self.last_model_notice = f"Modell {model} nicht verfuegbar, Fallback {fallback} genutzt."
                    LOGGER.warning(self.last_model_notice)
                    continue
                raise OpenAIServiceError(friendly) from exc
        raise OpenAIServiceError("; ".join(errors) or "OpenAI-Fehler ohne Detail.")

    def _send_responses(
        self,
        client,
        prompt: str,
        image_data_url: str | None,
        model: str,
        fallback_used: bool,
    ) -> tuple[str, UsageEstimate]:
        content = [{"type": "input_text", "text": prompt}]
        if image_data_url:
            content.append({"type": "input_image", "image_url": image_data_url})
        kwargs = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": [{"role": "user", "content": content}],
        }
        try:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "moodler_task_result",
                    "schema": RESULT_JSON_SCHEMA,
                    "strict": False,
                }
            }
            response = client.responses.create(**kwargs)
        except TypeError:
            kwargs.pop("text", None)
            response = client.responses.create(**kwargs)
        output = getattr(response, "output_text", None)
        raw = str(output if output is not None else response).strip()
        usage = build_usage_estimate("openai", model, getattr(response, "usage", None), prompt, raw, fallback_used)
        return raw, usage

    def _send_chat(
        self,
        client,
        prompt: str,
        image_data_url: str | None,
        model: str,
        fallback_used: bool,
    ) -> tuple[str, UsageEstimate]:
        if image_data_url:
            user_content: str | list[dict] = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            user_content = prompt
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
        except TypeError:
            response = client.chat.completions.create(model=model, messages=messages)
        content = response.choices[0].message.content
        raw = str(content or "").strip()
        usage = build_usage_estimate("openai", model, getattr(response, "usage", None), prompt, raw, fallback_used)
        return raw, usage

    def judge_results(self, results: list[TaskResult], source: str) -> TaskResult:
        valid_results = [result for result in results if result.task_type != "no_task" or result.full_answer]
        if not valid_results:
            return TaskResult.error("Alle Agentenlaeufe sind fehlgeschlagen.", source=source)

        prompt = self._build_judge_prompt(valid_results)
        try:
            raw, usage = self._send(prompt, image_data_url=None)
            judged = self._parse_result(raw, source)
            self._apply_usage(judged, usage)
        except Exception as exc:
            LOGGER.warning("Judge failed, using local fallback", exc_info=True)
            judged = self._local_judge(valid_results, source, str(exc))
        judged.agent_results = results
        judged.agent_summary = self._agent_summary(valid_results, judged)
        return judged

    def _parse_result(self, raw: str, source: str) -> TaskResult:
        data = safe_json_loads(raw)
        if data is None:
            return TaskResult.error(
                "Die KI-Antwort war kein gueltiges JSON. Oeffne Details, pruefe die Eingabe und versuche es erneut.",
                source=source,
            )
        return TaskResult.from_dict(data, raw_response=raw, source=source)

    def _build_judge_prompt(self, results: list[TaskResult]) -> str:
        packed = json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2)
        schema_text = json.dumps(JSON_SCHEMA_HINT, ensure_ascii=False, indent=2)
        return f"""Mehrere Agenten haben dieselbe Lernaufgabe beantwortet.

Entscheide niemals nach Mehrheit allein. Die Reihenfolge ist:
1. Aufgabe exakt erkennen.
2. Fachlich pruefen.
3. Antwortmoeglichkeiten einzeln verifizieren.
4. Erst danach Agentenantworten vergleichen.

Wenn Agenten widersprechen, entscheidet fachliche Richtigkeit, nicht Stimmenzahl.
Wenn keine Loesung sicher passt, setze short_answer auf "unsicher", senke confidence
und erklaere die Unsicherheit in warnings/full_answer.

MC:
- alle Optionen einzeln pruefen
- falsche Optionen kurz begruenden
- richtige Option fachlich nachweisen
- nur bei Eindeutigkeit Buchstaben in short_answer

Mathe:
- Gleichung, Brueche und Klammern streng lesen
- Antwortoptionen einsetzen
- rechnerisch verifizieren
- keine Agenten-Abstimmung

BW/RW:
- Kaufvertrag, Lieferung, Zahlung, Maengelruege, Mahnung, Verzug, Skonto,
  Rabatt, Bezugskalkulation, Absatzkalkulation, Buchungssaetze, Soll/Haben,
  Umsatzsteuer und Zahlungsverkehr fachlich/logisch pruefen.

Agenten-Antworten:
{packed}

Gib wieder ausschliesslich JSON nach diesem Schema zurueck:
{schema_text}"""

    def _local_judge(self, results: list[TaskResult], source: str, warning: str = "") -> TaskResult:
        best = max(results, key=lambda item: item.confidence)
        short_answers = {(item.short_answer or item.full_answer).strip().lower() for item in results}
        confidence = mean(item.confidence for item in results)
        if len(short_answers) == 1:
            confidence = min(0.85, confidence)
        else:
            confidence = min(0.45, best.confidence, confidence)
            best.short_answer = "unsicher"
            best.warnings.append("Agenten kamen zu unterschiedlichen Antworten; Mehrheit wurde nicht als Entscheidung verwendet.")
        if warning:
            best.warnings.append(f"Judge-Fallback ohne fachliche Vollpruefung: {warning}")
        best.confidence = confidence
        best.source = source
        return best

    @staticmethod
    def _agent_summary(results: list[TaskResult], final_result: TaskResult) -> str:
        lines = [
            f"Agenten: {len(results)}",
            f"Antworten verglichen: {len(results)}",
            f"Finale Antwort: {final_result.short_answer or final_result.full_answer}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _friendly_api_error(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        lowered = text.lower()
        if "timed out" in lowered or "timeout" in lowered:
            return "OpenAI/API-Timeout. Internet pruefen oder Timeout im Control Center erhoehen."
        if "api key" in lowered or "401" in lowered:
            return "OpenAI API-Key fehlt oder ist ungueltig. Bitte im Control Center pruefen."
        if OpenAIService._model_unavailable(exc):
            return "Modell nicht verfuegbar. Moodler versucht einen Fallback."
        if "connection" in lowered or "network" in lowered:
            return "OpenAI/API nicht erreichbar. Internetverbindung pruefen."
        return f"OpenAI-Fehler: {text[:220]}"

    def _build_prompt(self, source_type: str, mode_hint: str, text: str, exam_context: bool) -> str:
        mode_line = "auto erkennen" if mode_hint == "auto" else mode_hint
        schema_text = json.dumps(JSON_SCHEMA_HINT, ensure_ascii=False, indent=2)
        task_source = (
            "Analysiere den Screenshot. Lies sichtbaren Text/OCR selbst aus dem Bild."
            if source_type == "screenshot"
            else f"Analysiere diesen Text:\n{text}"
        )
        exam_note = (
            "Lokaler Hinweis: Der Text enthaelt moegliche Pruefungs-/Testbegriffe."
            if exam_context
            else "Kein lokaler Pruefungshinweis erkannt."
        )
        preferred_subjects = self._preferred_subjects_text()
        bw_context = self._bw_context_text()
        return f"""Aufgabe:
{task_source}

Gewuenschter Modus: {mode_line}
Bevorzugte Spracheinstellung: {self.settings.language}
Bevorzugte Faecher des Nutzers: {preferred_subjects}
{bw_context}
{exam_note}

Erkenne einen dieser task_type-Werte:
multiple_choice, true_false, gap_text, open_question, letter, email,
generic_text, summary, explanation, calculation, accounting, translation,
grammar, flashcards, no_task, incomplete_task.

Antwortlogik:
- multiple_choice: short_answer nur Buchstaben, z.B. "A C"; mehrere richtige Antworten sind erlaubt.
- MC-Richtigkeit: pruefe jede Option einzeln, begruende falsche Optionen in full_answer, short_answer nur bei eindeutiger Fachpruefung.
- true_false: short_answer nur "richtig" oder "falsch".
- gap_text: short_answer "Luecken ergaenzt", full_answer mit ausgefuelltem Text und Alternativen bei Unsicherheit.
- letter/email/generic_text/grammar: kopierbereiten Text in full_answer.
- summary: kurze Stichpunkte, wichtige Begriffe, keine unnoetigen Details.
- explanation: einfache HAK-Erklaerung, mit Beispiel wenn sinnvoll.
- calculation: Formel, Rechenweg, Ergebnis. short_answer ist das Endergebnis.
- Mathe-MC/calculation: Antwortoptionen einzeln einsetzen und rechnerisch pruefen; nicht raten.
- accounting: Buchungssatz/Kalkulation/BW-Loesung mit kurzer HAK-Erklaerung.
- BW/RW: Kaufvertrag, Lieferung, Zahlung, Maengelruege, Mahnung, Verzug, Skonto, Rabatt, Kalkulation, Buchungssaetze, Soll/Haben, Umsatzsteuer und Zahlungsverkehr streng fachlich pruefen.
- flashcards: sinnvolle Karteikarten in flashcards.
- no_task/incomplete_task: ehrlich melden, keine erfundene Aufgabe.

Menschlicher Schreibstil fuer letter/email/generic_text/summary/explanation/grammar/translation:
- Schreibe natuerlich wie ein guter HAK-Schueler, nicht wie ein KI-Text.
- Kurz, klar, glaubwuerdig, schulisch sauber, aber nicht uebertrieben perfekt.
- Keine langen Einleitungen und keine Floskeln wie "hiermit moechte ich Ihnen mitteilen", wenn sie nicht noetig sind.
- Bei Firma, Professor oder Amt hoeflich und sachlich; sonst direkt und menschlich.
- Briefe/E-Mails: sinnvoller Betreff, passende Anrede, kurzer Hauptteil, normale Schlussformel.
- Englisch: natuerliches Schulenglisch, einfache Woerter bevorzugen.

Confidence:
Nutze 0 bis 1. Senke confidence bei abgeschnittenen Screenshots, schlechter Lesbarkeit,
fehlendem Kontext, unklaren Antwortoptionen oder moeglichem Pruefungs-/Testkontext.
Fuege konkrete warnings hinzu, wenn etwas unsicher ist.

JSON-Schema:
{schema_text}

Gib ausschliesslich valides JSON zurueck."""

    def _preferred_subjects_text(self) -> str:
        subjects = self.settings.preferred_subjects or list(BW_FOCUS_SUBJECTS)
        return ", ".join(subjects) if subjects else "Betriebswirtschaft, Rechnungswesen, Mathematik"

    def _bw_context_text(self) -> str:
        topics = ", ".join(BW_FOCUS_TOPICS)
        return (
            "Der Nutzer ist HAK-Schueler. Priorisiere BW/Rechnungswesen/"
            "Kaufvertrag/Zahlungsverkehr/Mahnwesen. Pruefe fachlich korrekt, "
            "nicht per Mehrheit. HAK-BW-Themen: "
            f"{topics}."
        )

    def _candidate_models(self) -> list[str]:
        candidates = [self._model(), *MODEL_FALLBACKS]
        unique: list[str] = []
        for model in candidates:
            if model and model not in unique:
                unique.append(model)
        return unique

    @staticmethod
    def _model_unavailable(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(token in text for token in ["model", "not found", "does not exist", "404", "unsupported"])

    def _apply_service_warnings(self, result: TaskResult) -> None:
        if self.last_model_notice and self.last_model_notice not in result.warnings:
            result.warnings.append(self.last_model_notice)

    def _apply_usage(self, result: TaskResult, usage: UsageEstimate) -> None:
        result.provider = usage.provider
        result.model = usage.model
        result.input_tokens = usage.input_tokens
        result.output_tokens = usage.output_tokens
        result.total_tokens = usage.total_tokens
        result.estimated_cost_usd = usage.estimated_cost_usd
        result.provider_mode = self.settings.ai_provider
        result.fallback_used = usage.fallback_used

    def _api_key(self) -> str:
        return self.settings.openai_api_key or self.settings.api_key

    def _model(self) -> str:
        return self.settings.openai_model or self.settings.model
