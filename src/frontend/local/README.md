# Desktop frontend

The native client, for development on this machine. The browser client in
[`../public/`](../public/README.md) is the one a reviewer is given a link to;
[`../README.md`](../README.md) says why both exist and which rules they share.

The PySide6 client is a separate local process. It holds the visible chat state and makes the HTTP
calls. It imports no backend, LangChain, Ollama, search, or MLflow code.

Run it with `uv run --extra desktop python -m frontend.local.app`. `BACKEND_API_URL` defaults to
`http://127.0.0.1:8000`.

## What the owner sees

- The form asks for species and concern only. The backend asks the rest as its three standard
  questions.
- **Send concern** shows the concern at once as a right-aligned owner bubble, with a left-aligned
  "Thinking…" bubble while the request runs.
- Questions appear in left-aligned VetAI bubbles. Each answer appears as an owner bubble once the
  backend has accepted it.
- An emergency notice appears in a red VetAI bubble.
- An assessment appears as one wide VetAI bubble. It holds the outcome, what the owner reported,
  possible areas, suggested actions, questions for the veterinarian, and the sources. Each source
  is a link that opens in the web browser.
- The transcript scrolls to the newest bubble.

## Failures and retries

- A 422 shows the backend's field messages.
- A 503 or 500 shows the backend's fixed service text.
- No reply at all shows a connection or timeout message.
- In every case the typed answer stays in the box and **Try again** sends it again. There is no
  automatic retry.
- Until the first question arrives, the species and concern stay editable, so a failed first
  request can be corrected and sent again. After that they are locked.
- A concern or answer over 1,000 characters (the backend's limit) is refused with a message. It is
  never cut short, because the cut-off end could hold the words the emergency check looks for.
- An assessment or emergency notice ends the chat and shows **New concern**, which clears
  everything. A reply that arrives after **New concern**, or after a newer send, is ignored.

Qt marks every 4xx and 5xx reply as a network error. So `ChatApiClient._finished` checks for an
HTTP status first, and uses the connection message only when there is none.

## How the code is laid out

Two files:

- `api_client.py` sends one request and turns the reply into an `ApiResult`. It accepts a
  question, an emergency notice or an assessment, checks that every assessment field the window
  shows is present, and allows only `https://` source links.
- `app.py` holds the chat state and the window.
  - The state is a frozen `ChatState` changed only by `start_chat`, `request_body`, `accept` and
    `reject`. These follow the browser client's `chatState.js`, with one difference: the desktop
    shows the concern as the first bubble.
  - `transcript_html` turns the bubbles into HTML for one read-only `QTextBrowser`.
  - `ChatWindow._show` stores a new state and updates every widget from it.

Post-result "Ask another question" is deferred: it needs its own bounded, source-grounded contract.
