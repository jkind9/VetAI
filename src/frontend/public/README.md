# Browser client

A small Svelte page that gives the same chat as the desktop client without asking the visitor to
install anything. [`../README.md`](../README.md) says why it exists; this file is how to build and
serve it.

## Build

Node is needed to build the page, never to run the demo. The visitor needs only a browser.

```powershell
cd src/frontend/public
npm install
npm run build          # writes dist/
```

`dist/` is a folder of static files and is not committed. The backend serves it, so the page and the
API share one origin and there is no CORS configuration anywhere.

For UI work, `npm run dev` serves on port 5173 and proxies `/v1` and `/health` to
`http://127.0.0.1:8000`, so a backend started the usual way is reachable from the dev server.

The npm scripts call `node node_modules/vite/bin/vite.js` rather than the `vite` shim, because npm's
Windows shims fail when a parent directory name contains a space — as this repository's path does.

## Backend integration and current status

`src/backend/app.py` mounts `dist/` after `/v1/chat`, `/health`, and `/docs`, with `html=True` and a
directory-exists guard. The page and API therefore share one origin, while the backend still starts
normally when the browser bundle has not been built.

`src/lib/api.js` validates the structured `assessment` payload. The result component renders the
outcome, fixed wording, reported facts, possible areas when present, suggested actions,
veterinarian questions, resolved sources, and disclaimer. Malformed success payloads fail closed to
the stable service-error message.

## Full-process browser test

```powershell
cd src/frontend/public
npm run test:e2e
```

This builds the production Svelte bundle, starts a real FastAPI process on `127.0.0.1:8765`, and
drives Microsoft Edge through every question and answer. Dedicated cases cover the three-adaptive
question cap, `possible_problem`, `nothing_flagged`, deterministic emergency completion,
misspelled model escalation, and retryable model failure. The test uses the production workflow and
HTTP/static-serving layers with deterministic model and search adapters, so it verifies the complete
application path without making CI depend on Ollama or an external search provider. Real Ollama and
approved-source network checks remain separate opt-in smoke tests.

## Files

| File | Owns |
| --- | --- |
| `src/App.svelte` | The visible flow: intake, transcript, answer box, buttons, and the one `send` path |
| `src/lib/chatState.js` | The chat state machine, mirroring `ChatState` in `../local/app.py` |
| `src/lib/api.js` | The single `POST /v1/chat` call and the status-code to owner-text mapping |
| `src/lib/Bubble.svelte` | One transcript message, including structured assessment and sources |
| `src/lib/IntakeForm.svelte` | Species and concern only — the rest is asked in the chat |
| `vite.config.js` | Relative asset paths, `dist/` output, and the dev proxy |

`chatState.js` returns a new state from every function instead of editing one in place, so a reply
that arrives late can never half-apply to the chat now on screen. `assessment` and
`emergency_notice` are the only terminal API kinds.

## What it deliberately does not do

No routing, no store library, no streaming, no session storage, no build-time environment variables.
The page holds one chat in memory and forgets it on reload, which is the same lifetime the desktop
client has. There is no "ask another question" after a result: that needs its own bounded,
source-grounded contract, and it is deferred in both clients.
