# Source layout

The [backend](backend/README.md) owns validation, the emergency-first workflow, the deterministic
question prefix, three LangChain/Ollama stages, approved-source retrieval, grounding, and HTTP
composition. Uvicorn launches `backend.app:app`.

The [frontend](frontend/README.md) is a native PySide6 client. It owns in-memory conversation state,
separate owner/VetAI bubbles, pending/error states, and asynchronous HTTP. It imports no backend or
model/search package.

The backend remains stateless and stores no owner data. External search sees generated queries only;
the raw transcript stays local. MLflow tracking is the next planned source package after the chain
refactor.
