# VetAI technical test

I have read the brief's word *triage* as four jobs: sort the concern into one of three coarse
outcomes, gather the history a veterinarian would ask for, research the reported signs against
approved veterinary sources, and give the owner specific things to observe or record before any
appointment.

Those three outcomes are the only severity judgement the demo makes:

| Outcome | What the owner sees | Who decides it |
| --- | --- | --- |
| **Emergency** | A fixed notice to contact an emergency vet now | Two ordered checks are part of every turn: curated warning phrases matched by plain Python, then, if none match, a dedicated model check that judges whether the reported signs may need an emergency vet |
| **Possible problem, see a vet** | A recap of what was reported, points to raise, and the sources used | The model, from the owner's answers and the retrieved evidence |
| **Nothing flagged** | Nothing matched a warning sign and nothing was raised, plus what to watch for and when to go anyway | The model, within fixed wording the application supplies |

Escalation runs one way. On every turn, from the first message to the last answer before search,
the owner's words enter an ordered two-check process. First the phrase gate: plain Python, instant,
no model. Then, if no phrase matched, a model call with one job: decide whether the reported signs
may need an emergency vet now. Either can raise an emergency and neither can lower one. The model decides
*whether*, never the wording, so both routes return the same fixed notice. The model check covers
the phrase list's weakness, which is urgent wording the list does not contain: a pet's name, a
misspelling, a sign it does not name. It is told to answer yes when unsure, since a false alarm
sends someone to a vet they did not need. If the check itself fails, the turn stops with the
service error rather than continuing unchecked.

"Nothing flagged" is a statement about what this demo checked, not a clinical all-clear. It cannot
examine a pet, so it says what it found and what to keep an eye on, and never that a pet is well.

A small, source-grounded pet-concern demo. The desktop turns intake into a real conversation:
three short standard questions are followed by one to three adaptive LLM questions. Only after the
owner answers those questions does a separate LangChain step create web-search queries, retrieve
results from an approved veterinary-source list, and pass that evidence to a final synthesis chain.

The result separates what the owner reported, possible areas a veterinarian may consider,
source-backed suggested actions (including useful things to observe or record), questions to
discuss with a veterinarian, and the sources used.
Retrieved pages are background references rather than evidence that the animal has a condition.
The synthesis prompt requires a positive abnormal fact reported by the owner before it may return
`possible_problem`; pathology pages alone are not enough.
Curated emergency phrases in owner-written text still bypass every model and search step and return
a fixed emergency notice.

This is not a veterinary product. The three outcomes are a coarse routing decision, not a clinical
severity score, and the demo gives no diagnosis and no treatment advice. The phrase rules are
deliberately narrow: they can miss a real emergency and they can fire on misleading wording.

## Quickstart

Install [Ollama](https://ollama.com/) and download the default model once:

```powershell
ollama pull gpt-oss:20b
```

Ollama's desktop app normally starts its local service. If it is not running, start `ollama serve`
in a separate terminal and leave it open. Then, in two PowerShell terminals from this project
folder, run:

The backend automatically uses function calling for the default `gpt-oss:*` family because that is
how Ollama returns its structured results. Other model families retain the existing JSON-schema
mode. The gpt-oss reasoning effort is set to `low` so its bounded generation budget is reserved for
the typed response rather than exhausted before an answer is emitted.

```powershell
# Terminal 1: install dependencies and start the backend
uv sync --locked --extra desktop
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: open the desktop chat
uv run --extra desktop python -m frontend.local.app
```

Enter the pet's concern, select **Send concern**, and answer the questions shown in the chat. Owner
and VetAI messages appear in separate bubbles, with a visible pending state while a request is
running. The desktop connects to `http://127.0.0.1:8000` by default.

### Letting someone else use it

The backend, Ollama, and the model all stay on this machine. The intended reviewer path is the
browser client in [`src/frontend/public`](src/frontend/public/README.md), so the reviewer installs
nothing at all.

Build the page once, then put a temporary public URL in front of the running backend with
[cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/):

```powershell
# Once: build the browser client into src/frontend/public/dist
cd src/frontend/public; npm install; npm run build; cd ../../..

# Terminal 3: with the backend already running on port 8000
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints a `https://<random>.trycloudflare.com` address, and no Cloudflare account is needed. The
backend already serves the built page at `/` and the API at `/v1/chat`, so the tunnel needs only one
origin. `/docs` on the same address exposes the API. The browser client parses and renders the full
structured assessment contract, including the fixed outcome wording, suggested actions,
veterinarian questions, and resolved sources. Its production bundle and full question-to-assessment
path are covered by a hosted-backend Playwright test; see
[`src/frontend/public/README.md`](src/frontend/public/README.md) for commands and test boundaries.

Node is needed for that build step, never to run the demo. A visitor needs only a browser.

Two things to know before sharing the link. The address is minted per `cloudflared` process: it
changes every time the tunnel restarts and stops working the moment the process ends, so it suits a
live demo rather than a link committed anywhere. And it is public with no authentication or rate
limiting, so anyone holding it can run a chat against this machine. Start the tunnel when it is
wanted, and stop it afterwards.

- [Technical-test brief](e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf)
- [Implementation plan](documentation/implementation-plan.md)
- [Test cases and acceptable responses](documentation/test-cases.md)
- [Source layout](src/README.md)

The repository contains a runnable FastAPI backend, a native PySide6 desktop client, a Svelte
browser client, three versioned LangChain prompts, an Ollama adapter, an allowlisted search
adapter, MLflow tracking of every chat turn, and tests. The final scenario-based production
evaluation remains a planned milestone.

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
uv run --extra desktop python -m frontend.local.app
```

The client calls `http://127.0.0.1:8000` by default. Override the model, Ollama URL, timeout, or
desktop API URL without committing machine-specific values:

```powershell
$env:VETAI_OLLAMA_MODEL = "gpt-oss:20b"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:VETAI_OLLAMA_TIMEOUT_SECONDS = "60"
$env:BACKEND_API_URL = "http://127.0.0.1:8000"
```

The automated tests use a stand-in model. To check the real adapter, install
[Ollama](https://ollama.com/), pull the model, then run the opt-in test:

```bash
ollama pull gpt-oss:20b
VETAI_RUN_OLLAMA_SMOKE=1 uv run pytest tests/test_ollama_smoke.py -v -s
```

It prints the model's actual replies. Use `VETAI_OLLAMA_MODEL` to try a different tag.

Plain Python routes listed emergency phrases, the three standard questions, and the adaptive
question cap. On every turn not ended by the phrase gate, a standalone model chain checks for an
emergency before the workflow chooses the next question or starts search. It can raise an
emergency, but it cannot clear one. Search results are
filtered against [`config/approved_sources.toml`](config/approved_sources.toml), and the synthesis
model may cite only source IDs that the workflow actually retrieved. This provides provenance; it
does not clinically validate the generated text.
[`src/backend/README.md`](src/backend/README.md) walks through one turn and says where each rule
lives.

Each chat turn is stored on this machine in MLflow's database, `mlflow.db`. That includes the
owner's concern and answers, the generated search queries, and the page excerpts sent to the model.
The file is ignored by git; delete it to clear the history. The final search step sends only short,
model-derived search queries to the configured search service; the raw transcript stays local.
Retrieved page text is untrusted input even when it comes from an approved domain.

## See each turn in MLflow

Every chat turn is recorded as one MLflow run, with the exact prompts sent to the model, its
replies, and how long each step took. With the backend running and a chat done, start the MLflow UI
from the project root:

```powershell
uv run mlflow ui
```

Open http://127.0.0.1:5000 and choose the `vetai-chat` experiment. The Runs table has one row per
turn: the model, the prompt versions, the time taken and the kind of reply. The Traces tab shows
each turn's model calls. [`src/mlflow_tracking/README.md`](src/mlflow_tracking/README.md) lists
everything that is recorded.

## Conversation and chain order

```text
1. QUESTION LOOP
   owner concern or answer
      -> phrase emergency gate -> standalone emergency-check chain
      -> next fixed/adaptive question -> owner answers in a new turn -> repeat
      -> ready after 1 to 3 adaptive answers

2. SEARCH CHAIN
   search-query chain -> approved-source search -> validated evidence

3. SUMMARY + RECOMMENDATIONS
   evidence-synthesis chain -> grounded owner-visible result
```

The phrase gate can end a turn before the model is called. Otherwise the dedicated model check is
a link inside the question loop: it runs before the first question and again after every answer,
including the last answer before search. The three standard questions always come first. Search
never runs before at least one adaptive question has been answered. There is no automatic model
retry or default medical response. The search adapter repeats an entirely failed generated plan
once, without rephrasing or provider switching; any later failure leaves the owner's latest answer
available for a manual retry. See
[`documentation/failure-handling.md`](documentation/failure-handling.md) for the complete action
matrix and [`documentation/approved-sources.md`](documentation/approved-sources.md) for the source
policy.

## Docker: an example, not a deployment

We are not doing a Docker deployment. `Dockerfile` and `compose.yaml` are an example of how we would
do it, and they are not tested as part of this project. `compose.yaml` packages the backend and an
Ollama service; the PySide6 client remains native and connects through `http://127.0.0.1:8000`. The
named Ollama volume keeps downloaded models between container restarts.

```powershell
docker compose up --build -d
docker compose exec ollama ollama pull gpt-oss:20b
```

The compose file uses Ollama's official default image for local exploration. Set `OLLAMA_IMAGE` to
a pinned digest before relying on it for a reproducible environment. This is not a public-deployment
recipe: the demo has no authentication, rate limiting, or clinical-production safety controls.
