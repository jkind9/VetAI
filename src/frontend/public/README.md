# Browser page

A small Svelte page that gives the same chat as the desktop window, with nothing to install for the
person using it. [`../README.md`](../README.md) explains why it exists. This file covers building,
serving and testing it.

## Build

Node.js is needed to build the page, never to use it.

```powershell
cd src/frontend/public
npm install
npm run build          # writes dist/
```

`dist/` is a folder of static files and isn't committed. When it exists, the backend serves it at
`/`, from the same address as the API, so no cross-origin (CORS) setup is needed. If it doesn't
exist, the backend still starts.

For work on the page itself, `npm run dev` serves it on port 5173 and passes `/v1` and `/health`
requests on to the backend at `http://127.0.0.1:8000`.

The npm scripts run `node node_modules/vite/bin/vite.js` instead of the usual `vite` shortcut,
because npm's Windows shortcuts break when a folder in the path has a space, as this project's
path does.

## Test

```powershell
cd src/frontend/public
npm run test:e2e
```

This builds the page, starts a real backend on `127.0.0.1:8765` with a stand-in model and fake
search, and drives Microsoft Edge through six whole chats:

- a "possible problem" summary after all six questions;
- a "nothing flagged" summary;
- a failed search that still gives a summary with the search notice;
- an emergency caught by the phrase list;
- a misspelled emergency caught by the model check;
- a failed step, where the typed answer is kept and **Try again** works.

The real model and live search are tested separately (see [`tests/README.md`](../../../tests/README.md)),
so an outside service being down can't make this test fail.

## Files

| File | What it does |
| --- | --- |
| `src/App.svelte` | The visible chat: the form, the bubbles, the answer box, the buttons, and the one `send` function |
| `src/lib/chatState.js` | The chat state, mirroring `ChatState` in `../local/app.py` |
| `src/lib/api.js` | The one `POST /v1/chat` request, checking each reply's shape, and the text shown for each status code |
| `src/lib/Bubble.svelte` | One chat bubble, including the full summary with its sources and any search notice |
| `src/lib/IntakeForm.svelte` | The species and concern form |
| `vite.config.js` | The build output folder and the development proxy |

Every function in `chatState.js` returns a new state instead of changing the old one, so a reply
that arrives late can never half-update the chat on screen. A reply that doesn't have the expected
shape is shown as the fixed service error.

## Known gaps

- **Long text is cut short.** The concern and answer boxes use `maxlength="1000"`, so a browser
  silently cuts pasted text at 1,000 characters. The cut-off end could hold a warning phrase the
  emergency check never sees. The desktop window refuses over-long text with a message instead,
  which is the safe behaviour.
- **Try again after a failed first message.** If the very first message fails (for example, the
  backend is down), **Try again** doesn't resend it. The owner has to reload the page. The desktop
  window handles this case.
