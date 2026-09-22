# VetAI technical test

A small, source-grounded pet-concern demo. The desktop turns intake into a real conversation:
three short standard questions are followed by one to three adaptive LLM questions. Only after the
owner answers those questions does a separate LangChain step create web-search queries, retrieve
results from an approved veterinary-source list, and pass that evidence to a final synthesis chain.

The result separates what the owner reported, possible areas a veterinarian may consider, useful
things to observe or record, questions to discuss with a veterinarian, and the sources used.
Curated emergency phrases in owner-written text still bypass every model and search step and return
a fixed emergency notice.

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

Enter the pet's concern, select **Send concern**, and answer the questions shown in the chat. Owner
and VetAI messages appear in separate bubbles, with a visible pending state while a request is
running. The desktop connects to `http://127.0.0.1:8000` by default.

- [Technical-test brief](e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf)
- [Implementation plan](documentation/implementation-plan.md)
- [Test cases and acceptable responses](documentation/test-cases.md)
- [Source layout](src/README.md)

The repository contains a runnable FastAPI backend, a native PySide6 desktop client, three
versioned LangChain prompts, an Ollama adapter, an allowlisted search adapter, and tests. MLflow
tracking and the final scenario-based production evaluation remain planned milestones.

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

Plain Python routes listed emergency phrases, the three standard questions, and the adaptive
question cap. The model cannot choose the emergency route or search early. Search results are
filtered against [`config/approved_sources.toml`](config/approved_sources.toml), and the synthesis
model may cite only source IDs that the workflow actually retrieved. This provides provenance; it
does not clinically validate the generated text.
[`src/backend/README.md`](src/backend/README.md) walks through one turn and says where each rule
lives.

Nothing is stored by the current code. The final search step sends only short, model-derived search
queries to the configured search service; the raw transcript remains local. Retrieved page text is
untrusted input even when it comes from an approved domain. Planned MLflow runs will make every
chain and search step traceable and must stay out of Git.

## Conversation and chain order

```text
concern -> emergency check -> 3 standard questions -> 1-3 adaptive LLM questions
        -> search-query chain -> approved-source search -> evidence-synthesis chain -> result
```

The three standard questions always come first. Search never runs before at least one adaptive
question has been answered. There is no automatic model or search retry and no default medical
response: a failed stage leaves the owner's latest answer available for a manual retry. See
[`documentation/failure-handling.md`](documentation/failure-handling.md) for the complete action
matrix and [`documentation/approved-sources.md`](documentation/approved-sources.md) for the source
policy.

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
