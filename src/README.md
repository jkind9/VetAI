# Source layout

The implemented backend core is in [backend](backend/README.md): schemas, safeguards, workflow,
and the LangChain/Ollama adapter. The frontend folder currently contains design notes only.

The planned application is a PySide6 client calling a FastAPI backend over HTTP. The desktop would
own visible state and the API connection; the backend would own validation, emergency routing, and
model calls. Settings and MLflow tracking are not implemented yet.

See the [implementation plan](../documentation/implementation-plan.md) for the flow and trade-offs.
