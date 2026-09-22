# VetAI technical test

A small pet-concern demo. It accepts dog or cat intake, may ask up to two follow-up questions, and
then returns a model-written recap with a fixed non-diagnostic suffix. Curated emergency phrases in
owner-written text bypass the model and return a fixed emergency notice.

This is not a veterinary product. It gives no diagnosis, treatment advice, or urgency rating. The
phrase rules are deliberately narrow: they can miss emergencies or match misleading wording.

## Quickstart

Install [Ollama](https://ollama.com/) and download the default model once:

```powershell
ollama pull llama3:latest
```

Ollama's desktop app normally starts its local service. If it is not running, start `ollama serve`
in a separate terminal and leave it open. Then, in two PowerShell terminals from this project
folder, run:

```powershell
# Terminal 1: install dependencies and start the backend
uv sync --locked --extra desktop
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: open the desktop chat
uv run --extra desktop python -m frontend.app
```

Enter the pet's concern, select **Start chat**, and answer any follow-up questions. The desktop
connects to `http://127.0.0.1:8000` by default.

- [Technical-test brief](e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf)
- [Implementation plan](documentation/implementation-plan.md)
- [Test cases and acceptable responses](documentation/test-cases.md)
- [Source layout](src/README.md)

The repository contains a runnable FastAPI backend, a small native PySide6 desktop client, the
versioned prompt, Ollama adapter, and tests. Tracking and CI remain planned.

## Setup

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --extra desktop  # install the exact locked dependencies and native client
uv run pytest         # no model needed
uv run ruff check .   # lint
```

## Run locally

Ollama must be running separately. The backend and desktop are independent processes, so start
them in separate PowerShell terminals:

```powershell
# Terminal 1: FastAPI backend
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: native desktop client
uv run --extra desktop python -m frontend.app
```

The client calls `http://127.0.0.1:8000` by default. Override the model, Ollama URL, timeout, or
desktop API URL without committing machine-specific values:

```powershell
$env:VETAI_OLLAMA_MODEL = "llama3:latest"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:VETAI_OLLAMA_TIMEOUT_SECONDS = "60"
$env:BACKEND_API_URL = "http://127.0.0.1:8000"
```

The automated tests use a stand-in model. To check the real adapter, install
[Ollama](https://ollama.com/), pull the model, then run the opt-in test:

```bash
ollama pull llama3:latest
VETAI_RUN_OLLAMA_SMOKE=1 uv run pytest tests/test_ollama_smoke.py -v -s
```

It prints the model's actual replies. Use `VETAI_OLLAMA_MODEL` to try a different tag.

Plain Python routes listed emergency phrases and enforces the follow-up cap. The model supplies
text within the mode the workflow selected. Validation checks only the output's structure: an
allowed kind, and a non-blank reply within its length limit. It does not verify relevance, factual
grounding, or medical appropriateness; those remain prompt and human-review concerns.
[`src/backend/README.md`](src/backend/README.md) walks through one turn and says where each rule
lives.

Nothing is stored by the current code. Planned MLflow runs would contain owner-entered text and
must stay out of Git; delete their local `mlruns/` directory when it is no longer needed.

## Optional local Docker demo

`compose.yaml` packages the backend and an Ollama service; the PySide6 client remains native and
connects through `http://127.0.0.1:8000`. The named Ollama volume keeps downloaded models between
container restarts.

```powershell
docker compose up --build -d
docker compose exec ollama ollama pull llama3:latest
```

The compose file uses Ollama's official default image for local exploration. Set `OLLAMA_IMAGE` to
a pinned digest before relying on it for a reproducible environment. This is not a public-deployment
recipe: the demo has no authentication, rate limiting, or clinical-production safety controls.
