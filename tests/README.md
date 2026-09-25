# Tests

Run with `uv run pytest`. Ordinary tests need no model, network, or visible display. A stage-aware
fake records emergency-check, adaptive, query, and synthesis calls; a fake searcher supplies
approved and rejected evidence deterministically.

| File | Contract |
| --- | --- |
| `test_workflow.py` | The phrase gate followed by the standalone model emergency check on every unmatched turn; three fixed questions; adaptive cap; both assessment outcomes; chain ordering and short-circuiting |
| `test_questions.py` | Immutable question catalog and phase lookup |
| `test_search.py` | Query privacy checks, approved hosts, redirects, deduplication, three-results-per-query cap, retained sibling-query results, one bounded total-failure retry, and distinct no-results/no-evidence outcomes |
| `test_model_output.py` | Emergency/adaptive/query/synthesis structure, removal of adaptive `urgent_escalation`, outcome invariants, and citation-ID grounding failures |
| `test_scan_scope.py` | Emergency scan reads concern/owner answers only at every phase |
| `test_safeguards.py` | Curated phrase rules and near misses |
| `test_api.py` | Structured question/assessment/emergency responses, stable errors, and conditional Svelte static serving |
| `test_error_contracts.py` | Dedicated public `503`/`500` action-matrix paths, downstream-call boundaries, and no hidden retries |
| `test_approved_source_smoke.py` | Opt-in live fetch of a known MSD Veterinary Manual page through the production allowlist and page extractor |
| `test_frontend_state.py` | Desktop chat state: species-and-concern intake, accepted history versus draft, answer bubbles only after success, assessment/emergency end the chat |
| `test_frontend_window.py` | Offscreen desktop window: bubbles, "Thinking…" while pending, retry of a failed first or later request, assessment sections with a source link, reset |
| `test_frontend_api.py` | Desktop reply parsing (question, emergency, assessment, malformed bodies), and 422/503 bodies shown even though Qt flags them as network errors |
| `test_desktop_backend_contract.py` | The desktop's own requests sent to the real backend code, and its parsing of every real reply: question, emergency, assessment, 422, 503 |
| `test_mlflow_tracking.py` | One MLflow run per turn with its parameters, time and reply kind; failed and rejected turns marked FAILED with their reason; each turn's trace holds its LangChain prompt, reply and timing; overlapping turns keep their own traces; a turn is still answered, untraced, when its run cannot be opened; a failed MLflow write never changes the reply or turns a 422 into a 500; a deleted experiment is restored at startup; 48 turns at once are all answered and recorded |
| `test_runtime_app.py` / `test_settings.py` | Runtime composition, the model and prompt versions recorded on each MLflow run, and timeout/source configuration |
| `test_ollama_smoke.py` | Opt-in real-model adaptive question, query, outcome, and suggested-action shapes with fake evidence |
| `test_emergency_check_live.py` | Opt-in direct evaluation of the dedicated emergency chain: all seven emergency cases caught, no false alarms on the ordinary set, and aggregate MLflow metrics |
| `test_live_customer_journeys.py` | Recorded API journeys through real Ollama: J1 keyword emergency, J2 first-turn dedicated model emergency check, and J3 live search plus generated assessment |
| `../src/frontend/public/e2e/full-process.spec.js` | Production Svelte bundle through hosted FastAPI: adaptive cap, both outcomes, sources/actions, phrase/dedicated-model emergency routes, and retryable failure |

Case IDs and human-review rules live in
[`documentation/test-cases.md`](../documentation/test-cases.md).

External search is always faked in normal CI. The opt-in live customer journeys run a fixed
live-search scenario set separately and record provider/model versions, sources, latency, failures,
and human review.

```powershell
$env:VETAI_RUN_OLLAMA_SMOKE = "1"
$env:VETAI_OLLAMA_MODEL = "gpt-oss:20b"
uv run pytest tests/test_ollama_smoke.py -v -s
```

Every MLflow run the tests make goes to a throwaway database, never the project's `mlflow.db`. The
top of `conftest.py` sets `MLFLOW_TRACKING_URI` before any test imports `backend.app`, which starts
tracking as it is imported. The browser E2E server (`e2e_backend.py`) does the same.

The dedicated emergency-check quality evaluation is also opt-in. It calls the real configured
model directly for seven clear emergencies and seven ordinary statements, then records aggregate
MLflow metrics:

All opt-in model suites construct the adapter through the same settings-aware factory as the
launched backend, including model-family structured-output and reasoning settings.

```powershell
$env:VETAI_RUN_EMERGENCY_CHECK_LIVE = "1"
uv run pytest tests/test_emergency_check_live.py -v -s
```

The live approved-source check is separate from ordinary deterministic CI:

```powershell
$env:VETAI_RUN_LIVE_SEARCH_SMOKE = "1"
uv run pytest tests/test_approved_source_smoke.py -v
```

The browser E2E suite also stays separate from `pytest` because it builds the Svelte client and
launches Edge:

```powershell
cd src/frontend/public
npm run test:e2e
```

The real customer journeys are intentionally opt-in. They call the installed Ollama model and live
approved-source search, repeat J2/J3 three times, and write untracked JSON evidence to
`artifacts/live-journeys/`. A J3 artifact is not reviewer sign-off until its required human-review
checks are completed:

```powershell
$env:VETAI_RUN_LIVE_E2E = "1"
uv run pytest tests/test_live_customer_journeys.py -v -s
```
