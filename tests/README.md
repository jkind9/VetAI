# Tests

Run with `uv run pytest`. Ordinary tests need no model, network, or visible display. A stage-aware
fake records adaptive, query, and synthesis calls; a fake searcher supplies approved and rejected
evidence deterministically.

| File | Contract |
| --- | --- |
| `test_workflow.py` | Three fixed questions; mandatory first adaptive question; optional second/third; forced search at cap; chain ordering |
| `test_questions.py` | Immutable question catalog and phase lookup |
| `test_search.py` | Query privacy checks, approved hosts, redirects, deduplication, result limits, partial/all failure |
| `test_model_output.py` | Adaptive/query/synthesis structure and citation-ID grounding failures |
| `test_scan_scope.py` | Emergency scan reads concern/owner answers only at every phase |
| `test_safeguards.py` | Curated phrase rules and near misses |
| `test_api.py` | Structured question/assessment/emergency responses and stable errors |
| `test_frontend_state.py` | Accepted history versus draft, caps, assessment/end state, retry preservation |
| `test_frontend_window.py` | Separate bubbles, pending state, reset, and assessment sections offscreen |
| `test_frontend_api.py` | Nested assessment parsing and malformed response rejection |
| `test_runtime_app.py` / `test_settings.py` | Runtime composition and timeout/source configuration |
| `test_ollama_smoke.py` | Opt-in real-model chain shape with fake evidence search |

Case IDs and human-review rules live in
[`documentation/test-cases.md`](../documentation/test-cases.md).

External search is always faked in normal CI. A later productionisation milestone will run a fixed
live-search scenario set separately and record provider/model versions, sources, latency, failures,
and human review.

```powershell
$env:VETAI_RUN_OLLAMA_SMOKE = "1"
$env:VETAI_OLLAMA_MODEL = "gpt-oss:20b"
uv run pytest tests/test_ollama_smoke.py -v -s
```

MLflow tests are deferred until the chain contract is stable.
