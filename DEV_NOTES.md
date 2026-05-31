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
- Task warnings are saved in result/history/details instead of interrupting the flow.
- Token and cost metadata is stored per history row; dashboard totals are local estimates.
- Live provider balance is not claimed because neither desktop provider API exposes a simple universal balance endpoint here.

## Screenshot Selector

- [x] No dark fullscreen dimming overlay.
- [x] No green selection rectangle.
- [x] No fullscreen invisible input-capturing Toplevel.
- [x] No selection frame, border, overlay, text, or visible marker.
- [x] No global grabs or blocking waits.
- [x] Mouse and Esc/Right-click are polled through `root.after(...)`.
- [x] A low-level Windows mouse hook blocks the drag from reaching browsers/desktops, preventing blue text selection during capture.
- [x] Hook callbacks defer finish/cancel work back into Tk via `root.after(...)` to avoid destroying hook state inside the hook callback.
- [x] The hook is uninstalled on selection, Esc, right-click, timeout, and errors.
- [x] Escape is sent after cleanup to clear any accidental text selection.
- [x] No selector windows are created during area selection.
- [x] `Esc`, right-click, timeout, and small selections cancel and return the toolbar to `Ready`.
- [x] Selector timeout defaults to 20 seconds.

## Prompt Notes

- HAK/BW focus is internal and always active.
- Hidden preferred subjects are forced to the BW/HAK default list.
- Prompt always includes: HAK-Schueler, BW/RW, Kaufvertrag, Zahlungsverkehr, Mahnwesen, Kalkulation.
- OpenAI and Gemini use the same task JSON schema and the same HAK/BW context.
- Human writing style is required for letters, emails, summaries, explanations, translations, and generic texts.
- Provider modes are `openai`, `gemini`, `auto`, and `compare`.
- Auto mode falls back silently to the other configured provider and stores the notice in warnings/details.
- Compare mode asks both providers where keys are available and verifies fachlich, not by majority.
- Mathe-MC judge instructions require calculation/einsetzen instead of majority voting.
- BW/RW judge instructions require fachliche/logische Pruefung before comparing agents.
- Agent/Judge fallback marks divergent answers as `unsicher` instead of choosing a majority.
- Model fallback order is `gpt-4.1 -> gpt-4o -> gpt-4o-mini`.
- Gemini model fallback order is `gemini-2.5-flash -> gemini-2.0-flash`.
