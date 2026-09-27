# Desktop window

A PySide6 window for using the demo on this machine. It runs as its own process and talks to the
backend over HTTP. [`../README.md`](../README.md) explains why there is also a browser page, and
the rules both follow.

With the backend running:

```powershell
uv run --extra desktop python -m frontend.local.app
```

It connects to `http://127.0.0.1:8000`. Set `BACKEND_API_URL` to use another address.

## What the owner sees

- The form asks for species and concern only. The backend asks the rest as its three standard
  questions.
- **Send concern** shows the concern at once as an owner bubble on the right, with a "Thinking…"
  bubble while the request runs.
- Questions appear as VetAI bubbles on the left. Each answer appears as an owner bubble once the
  backend accepts it.
- An emergency notice appears in a red VetAI bubble.
- A summary appears as one wide bubble: the outcome, the search notice if the search didn't work,
  what the owner reported, points for the vet, suggested actions, questions for the vet, and the
  sources. Each source is a link that opens in the web browser.
- The chat scrolls to the newest bubble.

## When something goes wrong

- A `422` shows the backend's message about the field to fix.
- A `503` or `500` shows the backend's fixed service message.
- No reply at all shows a connection or timeout message.
- In every case the typed answer stays in the box, and **Try again** sends it again. Nothing is
  retried automatically.
- Until the first question arrives, the species and concern stay editable, so a failed first
  message can be corrected and sent again. After that they are locked.
- A concern or answer over 1,000 characters is refused with a message, never cut short.

Qt marks every 4xx and 5xx reply as a network error, which used to hide the backend's message. So
`ChatApiClient._finished` checks for an HTTP status first, and uses the connection message only
when there isn't one.

## How the code is laid out

- `api_client.py` sends one request and turns the reply into an `ApiResult`. It accepts a question,
  an emergency notice or a summary, checks that every summary field the window shows is present,
  and allows only `https://` source links.
- `app.py` holds the chat state and the window.
  - The state is a frozen `ChatState`, changed only by `start_chat`, `request_body`, `accept` and
    `reject`. These mirror the browser page's `chatState.js`, except that the desktop shows the
    concern as the first bubble.
  - `transcript_html` turns the bubbles into HTML for one read-only `QTextBrowser`.
  - `ChatWindow._show` stores a new state and updates every widget from it.
