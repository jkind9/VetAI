# Source code

| Folder | What it is |
| --- | --- |
| [`backend/`](backend/README.md) | The FastAPI app: the conversation rules, the emergency checks, the four model steps, web search, and the error replies |
| [`mlflow_tracking/`](mlflow_tracking/README.md) | Records every chat message as an MLflow run, with a trace of each model call |
| [`frontend/`](frontend/README.md) | The two chat screens: a browser page (Svelte) and a desktop window (PySide6) |

The screens only talk to the backend over HTTP (`POST /v1/chat`). Neither contains any model,
search or MLflow code, and the backend can't tell which screen it is talking to.

The backend keeps nothing between messages: each screen sends the whole chat every time. The only
thing saved is the MLflow record in `mlflow.db`, which stays on this machine and holds what the
owner typed. The web search only ever sees the short generated queries, never the chat.
