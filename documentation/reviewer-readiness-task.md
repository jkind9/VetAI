# Reviewer readiness task

Status: active

Objective: prepare VetAI for reviewer handoff against the original technical brief with one
production-equivalent model path, repeatable real-model journeys, inspected MLflow evidence, and an
up-to-date public repository.

## Current baseline — 2026-09-25

- `uv run pytest -q -rs`: 169 passed, 13 opt-in live checks skipped.
- `src/frontend/public`: 5 Playwright full-process journeys passed.
- Real `gpt-oss:20b` four-stage smoke: 4 passed with bounded fake evidence.
- Live approved-source smoke: passed.
- Current-model 14-case emergency evaluation: did not complete because its model construction
  path did not use the production structured-output and reasoning settings.
- Existing `artifacts/live-journeys/`: llama3-only; J3 remains 0/3 for human-review sign-off.
- Project MLflow database: 23 gpt-oss turn runs, 18 finished and 5 failed; the latest all-normal
  journey failed at evidence synthesis.

## Surgical work order

### 1. Align every real-model path with production — complete 2026-09-25

Named paths:

- `src/backend/model.py`
- `src/backend/app.py`
- `tests/test_model_adapter.py`
- `tests/test_ollama_smoke.py`
- `tests/test_emergency_check_live.py`
- `tests/test_live_customer_journeys.py`
- `tests/README.md`

Exit gate: the application and all three opt-in model suites construct `OllamaChatModel` through
one settings-aware factory, covered by a focused regression test. The 14-case emergency evaluation
must execute the same transport and reasoning configuration as the launched backend.

Evidence after alignment:

- focused factory/runtime gate: 10 passed;
- 14-case real-model emergency evaluation: passed;
- four-stage real-model smoke: 3 passed, synthesis failed closed on invalid gpt-oss output.

The remaining synthesis capability failure belongs to items 2 and 3; it is no longer obscured by
evaluation/runtime configuration drift.

### 2. Add the all-normal negative-control journey (J4)

Named paths:

- `documentation/test-cases.md`
- `tests/test_live_customer_journeys.py`
- `tests/live_journey_checks.py`
- `tests/test_j3_regression.py`
- `artifacts/live-journeys/`

Exit gate: three recorded production-runtime runs return `nothing_flagged`, contain no possible
areas or invented owner facts, and pass the documented human review.

Evaluation implementation: complete. The first valid `gpt-oss:20b` repetition set on 2026-09-27
was 0/3: run 1 failed closed on invalid synthesis output, run 2 failed closed on invalid query
output, and run 3 repeated the age question. The earlier connection-only attempts are not counted as
capability runs. Three live passes and human-review sign-off remain pending.

### 3. Make grounding and synthesis reliability measurable

Named paths:

- `prompts/evidence_synthesis.md`
- `src/backend/workflow.py`
- `src/backend/search.py`
- `src/backend/schemas.py`
- `tests/test_model_output.py`
- `tests/test_search.py`
- `tests/test_j3_regression.py`

Exit gate: owner facts cannot be authored from retrieved text, noisy page material is bounded to
relevant evidence, and unsupported or contradictory synthesis fails closed with a named test.

### 4. Complete MLflow quality evidence

Named paths:

- `src/mlflow_tracking/chat_runs.py`
- `src/mlflow_tracking/README.md`
- `tests/test_mlflow_tracking.py`
- `documentation/implementation-plan.md`

Exit gate: model, search, retrieval, and synthesis stages have inspectable timings and failure tags;
the release evidence reports terminal success, structured-output failures, outcome distribution,
and human-review status by model and prompt version.

### 5. Run the reviewer gate and publish the verified state

Named paths and evidence:

- `tests/README.md`
- `documentation/test-cases.md`
- `artifacts/live-journeys/`
- `mlflow.db`
- `README.md`
- public `origin/main`

Required gate:

1. deterministic Python suite green;
2. production-bundle Playwright suite green;
3. four-stage Ollama smoke green;
4. live approved-source smoke green;
5. 14-case emergency evaluation green;
6. J1 once, J2 three times, J3 three times, and J4 three times;
7. every J3/J4 artifact marked human-review `pass`;
8. one browser journey through the temporary public tunnel;
9. clean reviewed diff and public branch updated to the verified commit.

Work proceeds in the order above. Each runtime change uses a focused RED test, the smallest GREEN
implementation, then the relevant focused and full verification commands before the next item.
