# Desktop frontend

The PySide6 client is a separate local process. `app.py` owns its visible state and widgets;
`api_client.py` makes one asynchronous HTTP request per owner action. The client keeps the current
chat in memory, starts a new flow after a summary or emergency notice, preserves an answer for a
manual retry, and never retries a model call automatically.

The HTTP client uses Qt's asynchronous
[`QNetworkAccessManager`](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QNetworkAccessManager.html).
It reads only `BACKEND_API_URL` and does not import backend logic, LangChain, Ollama, or MLflow.

Run it with `uv run --extra desktop python -m frontend.app`. Set `BACKEND_API_URL` to use a backend
other than the default `http://127.0.0.1:8000`.
