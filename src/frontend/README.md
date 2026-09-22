# Desktop frontend

This folder has design notes only; the PySide6 client is not implemented. The planned client keeps
the current chat in memory, sends each turn to a FastAPI endpoint, and starts a new flow after a
summary or emergency notice. It should preserve an answer for manual retry and never retry a model
call automatically.

The planned HTTP client uses Qt's asynchronous
[`QNetworkAccessManager`](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QNetworkAccessManager.html).
It reads only `BACKEND_API_URL` and does not import backend logic, LangChain, Ollama, or MLflow.

The proposed interaction is in the [plan](../../documentation/implementation-plan.md).
