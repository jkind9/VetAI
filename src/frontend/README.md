# Desktop frontend

The PySide6 client is a separate local process. It owns visible chat state and asynchronous HTTP;
it imports no backend, LangChain, Ollama, search, or future MLflow code.

The initial intake contains only species and concern. Selecting **Send concern** immediately adds a
right-aligned owner bubble and a visible VetAI pending state. Standard and adaptive questions appear
in left-aligned VetAI bubbles. Each later answer is rendered separately as an owner bubble, so model
and owner text are never mixed in one transcript block.

The scrollable conversation surface has one vertical message layout:

- owner bubbles: right aligned, high-contrast accent surface;
- VetAI bubbles: left aligned, quiet neutral surface;
- pending state: left aligned status text such as “Thinking…” or “Reviewing answers and approved
  sources…”;
- assessment: a wider assistant surface with labelled sections for reported facts, possible areas,
  useful observations, veterinarian questions, and sources.

The desktop keeps accepted pairs separate from the draft for the current question. A successful
response commits the pair. On validation, model, search, synthesis, connection, or timeout failure,
the exact draft remains editable and **Try again** appears. There is no automatic retry.

Assessment and emergency responses end the chat and show **New concern**. Starting over clears the
intake, history, bubbles, errors, and pending state. Late responses from an abandoned request are
ignored by request ID.

Post-result “Ask another question” is intentionally deferred; it needs a separate bounded and
source-grounded contract. The current completed state contains **New concern** only.

Run with `uv run --extra desktop python -m frontend.app`. `BACKEND_API_URL` defaults to
`http://127.0.0.1:8000`.
