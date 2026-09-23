# Frontend

Two clients, one API. Neither imports backend, LangChain, Ollama, search, or MLflow code; both
speak the same `POST /v1/chat` contract and map the same status codes to the same owner-facing text.

| Folder | Client | Who it is for |
| --- | --- | --- |
| [`local/`](local/README.md) | Native PySide6 desktop window | Development on this machine |
| [`public/`](public/README.md) | Svelte page served by the backend | Anyone given a link, with nothing to install |

## Why there is a second, browser-based client

The desktop client cannot be shared. PySide6 draws to the operating system's window manager, so
there is no port to forward and no page to hand out — to see it, a person has to install Python,
`uv`, Qt and Ollama, then pull a multi-gigabyte model, before anything appears on screen. For a
reviewer who wants to spend ten minutes looking at this project, that is the whole ten minutes.

The Svelte client removes all of it. The backend serves the built page from the same origin as the
API, so one Cloudflare tunnel in front of port 8000 is the intended reviewer demo: the visitor opens
it and the model runs on the machine hosting the backend. They install nothing, configure nothing,
and pull no model. The static mount and structured assessment rendering are implemented. A browser
E2E test exercises the production bundle, every question turn, both assessment outcomes, sources,
suggested actions, and the emergency route against a locally hosted FastAPI process. The root
README's "Letting someone else use it" section has the tunnel commands.

Two smaller reasons it earns its place. It proves the frontend/backend boundary is real rather than
asserted — the same JSON contract drives a Qt window and a browser page, and the backend cannot tell
them apart. And it is the client a hosted deployment would use later, so the option stays open
without a rewrite.

Svelte rather than a plain HTML file because the chat has genuine state to keep straight — pending
turns, a draft answer that must survive a failed request, late replies from abandoned requests — and
that logic reads better as components with reactive state than as hand-written DOM updates. It costs
one build step and no runtime dependency: the output is static files.

## What each client owns

Both hold the same shape of visible state: the current intake, the accepted question-and-answer
pairs, the draft answer for the question on screen, a pending flag, an ended flag, and the last
error. The rules they both follow:

- an answer joins the history only once the backend has accepted it;
- a failed turn leaves the draft exactly as typed, and retrying is always the owner's action;
- an assessment or emergency notice ends the chat, and starting over clears everything;
- a reply from a superseded or abandoned request is dropped by request id.

Every decision about *what* the owner sees next is the backend's: the emergency route, which
question comes next, and when the conversation ends. Neither client can reach those rules.
