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

Additional phrase-gate correction complete: ingestion verbs now require a leading word boundary,
and the urination alternatives require a trailing boundary. This prevents `ate` inside `rate` and
`wee` inside `week` from selecting an emergency route while preserving the curated positive cases.
The focused safeguard matrix is 20/20.

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

After the assessment-alias repair and duplicate-question guard, a new 0/3 set reached query and
synthesis on every run; all three then failed closed on invalid synthesis output. This isolates the
current J4 blocker to the assessment response shape rather than emergency, adaptive, query, or
retrieval routing.

The synthesis prompt now explicitly requires useful cited actions and veterinarian questions for
`nothing_flagged`. An exact recorded-input replay passed, and the next J4 set produced one automated
and human-reviewed pass. Runs 2 and 3 failed after both bounded live-search provider attempts, so
the current aggregate is 1/3 rather than a model-selected false positive.

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

First adapter reliability increment complete: a reproduced gpt-oss assessment tool call used
`area`, `action`, and `question` for the shared nested `text` field. The adapter now normalises only
those three known labels and reruns the strict schema; the previously failing real query/synthesis
smoke passes. A subsequent deterministic guard now treats an exact later question repeat as
readiness; all three follow-up J4 runs reached synthesis, where a separate structured-output
failure remained. Requiring non-empty useful sections for `nothing_flagged` resolved the reproduced
shape; the remaining two failures in the latest set are at live search.

#### Demo-readiness pass — 2026-09-27 afternoon

The owner ruled that reasonable, widely accepted general veterinary guidance is acceptable when it
does not contradict the retrieved sources. That replaced the stricter review rule under which the
13:08 set scored J3 0/3 and J4 1/3 (flushed face, routine checks and similar details were failed
only for not appearing on the cited page).

Changes, each with a failing test first:

1. Synthesis prompt v2 allows that general guidance; the human-review checklist matches it.
2. Search retries use exponential backoff (1, 2, 4 s), and a retry starts only if it should finish
   inside a 20 s search budget.
3. A search-service failure no longer ends the turn. The summary is written from general guidance
   with a "search did not work" notice and no sources. An unsafe query or an unexpected searcher
   bug still returns an error, and uncited items are rejected whenever sources were found.
4. The model now has a 16,384-token context window. Ollama's default of about 2,048 tokens silently
   dropped the start of any longer synthesis prompt, including the rules and owner report. Every
   failed synthesis in the 13:30 set had exactly 2,050 prompt tokens and failed 3/3 on replay (empty
   reply, or an invented "pubmed" tool call); with the larger window the same inputs pass.

Live results on gpt-oss:20b after all four changes (13:39 set), each reviewed by hand:

| Run | Automated | Human review | Note |
| --- | --- | --- | --- |
| J3 run 1 | pass | pass | The scripted harness gave one answer twice; not an app defect |
| J3 run 2 | fail | fail | Search service down on all 4 attempts; the fallback summary and notice worked |
| J3 run 3 | pass | pass | One source title joins several page titles together (cosmetic) |
| J4 run 1 | pass | pass | |
| J4 run 2 | pass | pass | |
| J4 run 3 | pass | pass | |

J3 is 2/3 and J4 is 3/3. The remaining J3 failure depends on the external search service.

### 4. Complete MLflow quality evidence

Named paths:

- `src/mlflow_tracking/chat_runs.py`
- `src/mlflow_tracking/README.md`
- `tests/test_mlflow_tracking.py`
- `documentation/implementation-plan.md`

Exit gate: model, search, retrieval, and synthesis stages have inspectable timings and failure tags;
the release evidence reports terminal success, structured-output failures, outcome distribution,
and human-review status by model and prompt version.

Default-database path correction complete: when `MLFLOW_TRACKING_URI` is unset, backend startup now
selects the literal relative URI `sqlite:///mlflow.db` before creating the MLflow client. This
prevents project paths containing spaces or `&` from being percent-encoded into a different sibling
directory, while preserving explicit environment configuration. Unit coverage checks both paths;
an isolated smoke created and used `mlflow.db` inside a temporary directory containing both
characters. Stage-timing and release-summary evidence in the exit gate remain pending.

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

Gate 8 passed on 2026-09-27 against the relaunched production bundle through a temporary
Cloudflare tunnel. A headless Edge journey submitted the deterministic breathing-emergency case,
received the fixed notice, and produced FINISHED MLflow run
`cc9718a5b40f4a9ba037ad1d082972e2` with model `gpt-oss:20b` and reply kind
`emergency_notice` in the project-root `mlflow.db`. The older percent-encoded sibling database was
unchanged.

Work proceeds in the order above. Each runtime change uses a focused RED test, the smallest GREEN
implementation, then the relevant focused and full verification commands before the next item.
