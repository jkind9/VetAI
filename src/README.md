# Source layout

The [backend](backend/README.md) owns validation, the emergency-first workflow, the deterministic
question prefix, three LangChain/Ollama stages, approved-source retrieval, grounding, and HTTP
composition. Uvicorn launches `backend.app:app`.

The [frontend](frontend/README.md) is two clients over one API: a native PySide6 desktop window in
`frontend/local` for work on this machine, and a Svelte page in `frontend/public` that the backend
serves so anyone given a link can use the demo with nothing installed. Each client owns in-memory
conversation state, separate owner/VetAI bubbles, pending/error states, and asynchronous HTTP.
Neither imports any backend, model, or search package.

The [MLflow tracking](mlflow_tracking/README.md) package records every chat turn as an MLflow run,
with the turn's LangChain calls traced inside it. All MLflow code lives there.

The backend keeps no session between turns. Each turn's record, including owner text, is stored on
this machine in MLflow's `mlflow.db`, which git ignores. External search sees generated queries
only; the raw transcript stays local.
