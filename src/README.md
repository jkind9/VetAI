# Source layout

The implemented [backend](backend/README.md) owns request validation, emergency routing, workflow
decisions, and the LangChain/Ollama adapter. It is launched by Uvicorn from `backend.app:app`.

The implemented [frontend](frontend/README.md) is a native PySide6 client. It owns the visible
chat state and asynchronous HTTP connection to the backend; it does not import backend code.

Settings are read from environment variables at backend launch. MLflow tracking remains planned.
See the [implementation plan](../documentation/implementation-plan.md) for the flow and trade-offs.
