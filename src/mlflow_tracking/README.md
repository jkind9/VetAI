# MLflow tracking

Everything MLflow-related lives in this folder. The backend records every chat turn here, so the
prompts sent to the model, the model's replies, and how long each step took can be looked at
later. This is the technical-test brief's MLflow requirement.

## What is recorded

Each chat turn (one `POST /v1/chat`) is one MLflow **run** in the `vetai-chat` experiment:

| Kind | Name | Meaning |
| --- | --- | --- |
| parameter | `model` | the Ollama model tag, for example `llama3:latest` |
| parameter | `adaptive_question`, `search_query`, `evidence_synthesis` | a SHA-256 of each prompt file, so runs made with different prompt text can be told apart |
| parameter | `species` | dog or cat |
| parameter | `answered_questions` | how many questions the owner had answered before this turn (0 to 6) |
| metric | `turn_seconds` | how long the turn took |
| tag | `reply_kind` | `question`, `assessment` or `emergency_notice` |
| tag | `failed_stage`, `failure_reason` | only on a failed turn, whose run is marked FAILED |

Each run holds one **trace**:

- Its top span, `chat_turn`, holds the request and the result.
- Inside it, every LangChain call the turn made has its own span with the exact prompt sent, the
  model's reply, and how long it took. Those calls are the adaptive-question, search-query and
  evidence-synthesis chains.
- The web search and page fetching between those calls has no span yet.

The `run_id` in each successful chat response is that turn's run, for looking it up in the UI.

## See it

Start the backend from the project root and have a chat. Then, in another terminal, also from the
project root:

```powershell
uv run mlflow ui
```

Open http://127.0.0.1:5000 and choose the `vetai-chat` experiment. The Runs table has one row per
turn, and the Traces tab has one trace per turn.

## Where the data goes

- MLflow writes to `MLFLOW_TRACKING_URI` when it is set. Otherwise it writes to `mlflow.db` in the
  folder the backend was started from. `mlflow ui` reads that same file by default, so start both
  from the project root.
- The example Docker image (not a supported deployment) sets
  `MLFLOW_TRACKING_URI=sqlite:////home/vetai/mlflow.db`, because its user
  cannot write to `/app`. Those runs are lost when the container is removed.
- The runs contain owner text: the concern, the answers, the generated search queries, and the
  page excerpts sent to the model. `mlflow.db` is ignored by git and Docker. Delete it to clear the
  history.
- The tests and the browser test server point MLflow at a throwaway database, so they never write
  to the project's `mlflow.db`.

## How the code works

`chat_runs.py` has two functions:

- `start_tracking()` chooses the `vetai-chat` experiment and turns on `mlflow.langchain.autolog()`,
  which traces every LangChain call from then on. It also makes MLflow save each trace before the
  turn returns, rather than in the background. `backend.app.create_runtime_app` calls it once when
  the server starts.
- `run_tracked_turn(turn, chains, searcher, run_params)` runs one turn inside an MLflow run and
  returns the result with the run's id. The chat route in `backend/app.py` calls it for every
  request.

Behaviours to know about:

- MLflow links a new trace to the latest open run in any thread. When two turns overlap, that is
  the wrong run. So the turn's span is started with `run_id=`, which ties its trace to its own run.
- With MLflow's default background saving, some traces were written as files under `./mlruns`
  instead of into `mlflow.db`. That splits the data in two, and `/app` is not writable in the
  Docker image. Saving each trace before the turn returns keeps everything in the one database
  file. In the real-model check, turns with no model call still took under 0.1 seconds including
  the save.
- Opening a run can fail without costing the owner a reply. This follows the usual rule for
  tracking and telemetry: lose the record rather than change what the app does. Later MLflow
  writes are not covered yet.
  - If MLflow cannot open a run, for example because the database file is read-only, the turn is
    answered without one. The error goes to the server log, and the reply's `run_id` is `null`.
  - A failure after the run has opened still ends that turn with the 500 service error. Examples:
    someone deletes the experiment mid-turn, or the database is briefly locked under load. A
    rejected request (422) can also become a 500 this way.
  - A turn answered without a run still traces its model calls, and MLflow may file that trace
    under another turn's open run. So under MLflow trouble, one run can hold another turn's
    prompts.
- The MLflow UI's Delete button only moves the experiment to a bin, and MLflow refuses to use a
  binned experiment or reuse its name. `start_tracking()` brings a binned `vetai-chat` back when
  the server starts.
- MLflow's default pool of 15 shared database connections ran out when about 48 turns arrived at
  once: requests failed after a 30-second wait. `start_tracking()` makes MLflow open a new
  connection for each use (`NullPool`).
- Every failed turn's run says why. A model, search or grounding failure records `failed_stage`
  and `failure_reason`. A rejected history (422) or an unexpected crash (500) records the error's
  type as `failure_reason`.

## Not done yet

- a span for the web search and page fetching;
- per-stage timings as run metrics (they are already visible per span in the trace);
- a run id in error responses;
- an analysis script over the recorded runs;
- moving the live customer-journey test's hand-built recording onto MLflow;
- making MLflow writes after the run opens unable to fail the turn, and stopping a turn without a
  run from filing its trace under another run.
