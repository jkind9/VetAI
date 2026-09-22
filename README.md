# VetAI technical test

A small pet-concern demo. It accepts dog or cat intake, may ask up to two follow-up questions, and
then returns a model-written recap with a fixed non-diagnostic suffix. Curated emergency phrases in
owner-written text bypass the model and return a fixed emergency notice.

This is not a veterinary product. It gives no diagnosis, treatment advice, or urgency rating. The
phrase rules are deliberately narrow: they can miss emergencies or match misleading wording.

- [Technical-test brief](e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf)
- [Implementation plan](documentation/implementation-plan.md)
- [Test cases and acceptable responses](documentation/test-cases.md)
- [Source layout](src/README.md)

The repository currently contains the decision core, versioned prompt, Ollama adapter, and tests.
The FastAPI route, settings, tracking, desktop client, and CI workflow are still planned, so there
is no end-to-end application to launch.

## Setup

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked      # install the exact locked dependencies
uv run pytest         # no model needed
uv run ruff check .   # lint
```

The automated tests use a stand-in model. To check the real adapter, install
[Ollama](https://ollama.com/), pull the model, then run the opt-in test:

```bash
ollama pull llama3:8b
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
