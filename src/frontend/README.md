# Frontend

Two chat screens use the same backend. Neither contains any model, search or MLflow code. Both
send the same `POST /v1/chat` request and show the same text for each kind of reply.

| Folder | Screen | Who it is for |
| --- | --- | --- |
| [`public/`](public/README.md) | A browser page (Svelte), served by the backend | Anyone given a link, with nothing to install |
| [`local/`](local/README.md) | A desktop window (PySide6) | Working on this machine |

## Why there are two

The desktop window came first. It can't be shared: to see it, someone has to install Python, uv,
Qt and Ollama, and download a 13 GB model. The browser page removes all of that. The backend
serves the page from the same address as the API, so one temporary public link (see the root
README) lets a reviewer use the demo in a browser while the model runs on the host machine.

Having two screens also shows that the boundary between screen and backend is real: the same
requests drive a desktop window and a web page, and the backend can't tell them apart.

The page uses Svelte rather than hand-written HTML and JavaScript because the chat has state to
keep straight: a pending request, a typed answer that must survive a failed request, and late
replies from requests the owner has moved on from. Svelte builds to plain static files, so it adds
a build step but nothing extra at runtime.

## Rules both screens follow

Both keep the same things in memory: the species and concern, the accepted questions and answers,
the answer being typed, whether a request is pending, whether the chat has ended, and the last
error.

- An answer joins the history only after the backend accepts it.
- A failed request leaves the typed answer exactly as it was. Retrying is always the owner's
  choice, with **Try again**.
- A summary or an emergency notice ends the chat. **New concern** clears everything.
- A reply that arrives after **New concern**, or after a newer request, is ignored.
- Text over 1,000 characters must be refused with a message, never cut short, because the cut-off
  end might contain a warning phrase. The desktop window does this. The browser page doesn't yet:
  its text boxes stop at 1,000 characters, which silently cuts pasted text (see its README).
- A `422` shows the backend's message about the field to fix. A `503` or `500` shows the fixed
  service message, and no reply at all shows a connection or timeout message.
- When the summary has no sources because the search didn't work, the search notice is shown and
  the empty citations and "Sources" heading are hidden.

Both screens stop waiting after 65 seconds. Everything about what the owner sees next (emergencies,
which question comes next, when the chat ends) is decided by the backend.
