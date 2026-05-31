# Moodler Dev Notes

## Old-Bar Regression Checklist

- [x] `root.geometry("200x50+5+5")`
- [x] `root.overrideredirect(True)`
- [x] `root.attributes("-topmost", True)`
- [x] Transparent color key `#010101`
- [x] Toolbar frame height `50`
- [x] Frame pack `fill="x", expand=False, padx=1, pady=1`
- [x] Status row minsize `25`
- [x] Button row minsize `25`
- [x] Status font `("Arial", 7)`
- [x] Status color `#2a2a2a`
- [x] Button bg `#2a2a2a`
- [x] Button fg `#4a4a4a`
- [x] Button active bg `#3a3a3a`
- [x] Button active fg `#5a5a5a`
- [x] Button font `("Arial", 6)`
- [x] Button padding `padx=3, pady=1`
- [x] Button pack `side="left", padx=1`
- [x] Main-Bar buttons only: `1x/2x`, camera icon, send arrow, settings gear, unchanged reset-arrow button, quit x
- [x] No tooltip class, no hover text, no hover Toplevels
- [x] Long text/features live behind the old settings gear / Control Center
- [x] Reset-arrow button no longer deletes API keys; it only moves the toolbar for the current session.

## Toolbar Position

- [x] Start position is always `200x50+5+5`.
- [x] Stored `toolbar_x` and `toolbar_y` are ignored for startup.
- [x] Move button changes position only for the current session.
- [x] Normal and result-width geometry keep the current session X/Y.
- [x] API key deletion exists only in Control Center > API.

## Start Behavior

- [x] Missing API key only sets toolbar status `API fehlt`.
- [x] Control Center does not open automatically on startup.
- [x] First send without API key opens the API tab without a task popup.
- [x] Toolbar gets `WS_EX_LAYERED`, `WS_EX_TOOLWINDOW`, and `WS_EX_NOACTIVATE` on Windows.

## Stability Notes

- API work runs in background threads.
- Screenshot capture runs outside the Tk callback after selection.
- UI updates return through `root.after(...)`.
- OpenAI client uses configured timeout.
- Long answers are copied silently when Auto-Copy is active.
- Calculation/accounting results store `copied_value`; calculation copies the final value, accounting copies the booking entry when detected.
- Task warnings are saved in result/history/details instead of interrupting the flow.
- Token and cost metadata is stored per history row; dashboard totals are local estimates.
- Live provider balance is not claimed because neither desktop provider API exposes a simple universal balance endpoint here.
- SEB support is detection-only: Moodler checks running process names for status display, but does not bypass, hide from, alter, or weaken Safe Exam Browser restrictions.

## Screenshot Selector

- [x] Uses the old stable Moodler principle: fullscreen `tk.Toplevel`, `alpha=0.01`, black background, `Canvas`.
- [x] Uses normal Tk bindings: `<ButtonPress-1>`, `<B1-Motion>`, `<ButtonRelease-1>`, `<Escape>`.
- [x] No low-level Windows mouse hook.
- [x] No input polling loop.
- [x] No `grab_set`, `wait_window`, or `wait_variable`.
- [x] No green selection rectangle.
- [x] No drawn selection frame, border, text, or marker.
- [x] The nearly transparent Canvas catches drag events, preventing browser text selection.
- [x] Coordinates are calculated from `event.x_root`/`event.y_root` and converted with current DPI scale.
- [x] On release the selector calls `withdraw()`, waits 150 ms, destroys itself, then hands coords back.
- [x] Screenshot capture still runs afterward in a worker thread.
- [x] `Esc`, right-click, and small selections cancel and return the toolbar to `Ready`.

## Prompt Notes

- HAK/BW focus is internal and always active.
- Hidden preferred subjects are forced to the BW/HAK default list.
- Prompt always includes: HAK-Schueler, BW/RW, Kaufvertrag, Zahlungsverkehr, Mahnwesen, Kalkulation.
- OpenAI and Gemini use the same task JSON schema and the same HAK/BW context.
- OpenAI and Gemini use the same prompt builder; letter/email extraction rules are not duplicated per provider.
- Human writing style is required for letters, emails, summaries, explanations, translations, and generic texts.
- Letter/email prompts require reading recipient, contact person, subject, numbers, dates, deadlines, product, quantity, defect/reason and requested action without inventing missing data.
- Provider modes are `openai`, `gemini`, `auto`, and `compare`.
- Auto mode falls back silently to the other configured provider and stores the notice in warnings/details.
- Compare mode asks both providers where keys are available and verifies fachlich, not by majority.
- Hard tasks auto-escalate to OpenAI + Gemini when both keys exist: MC, calculation, accounting/BW and uncertain screenshot results.
- Mathe-MC judge instructions require calculation/einsetzen instead of majority voting.
- BW/RW judge instructions require fachliche/logische Pruefung before comparing agents.
- Agent/Judge fallback marks divergent answers as `unsicher` instead of choosing a majority.
- Uncertainty retry runs at most three analysis attempts; after that unresolved tasks stay `unsicher`.
- Model fallback order is `gpt-4.1 -> gpt-4o -> gpt-4o-mini`.
- Gemini model fallback order is `gemini-2.5-flash -> gemini-2.0-flash`.
