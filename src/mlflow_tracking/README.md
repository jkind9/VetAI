# MLflow tracking

The brief asks for MLflow to track the prompts, the model's responses, and the timing, and for
some analysis of them. This folder does that. Every message the owner sends (one `POST /v1/chat`,
called a "turn") is recorded as one MLflow run, and all the MLflow code lives here.

## What is recorded

Each turn is one **run** in the `vetai-chat` experiment:

| Kind | Name | What it holds |
| --- | --- | --- |
| parameter | `model` | The Ollama model, for example `gpt-oss:20b` |
| parameter | `emergency_check`, `adaptive_question`, `search_query`, `evidence_synthesis` | A SHA-256 fingerprint of each prompt file, so runs made with different prompt text can be told apart |
| parameter | `species` | Dog or cat |
| parameter | `answered_questions` | How many questions the owner had answered before this turn (0 to 6) |
| metric | `turn_seconds` | How long the turn took |
| tag | `reply_kind` | `question`, `assessment` or `emergency_notice` |
| tag | `failure_reason` | Only on a failed turn, whose run is marked FAILED: why it failed. For an unexpected error or a rejected history, this is the error's type name |
| tag | `failed_stage` | Only when a named step failed (a model call, the search or the citation check): which step |

Each run also holds one **trace**, which shows the prompts and replies:

- The top step, `chat_turn`, holds the whole request and the reply.
- Inside it, each model call has its own step, with the exact prompt sent, the model's reply, and
  how long it took. A standard-question turn has one model call, the emergency check. A follow-up
  turn has the emergency check and the follow-up question. The final turn adds the search queries
  and the summary.
- A turn ended by the emergency phrase list has no model calls, so its trace has only the top step.
- The web search and page downloads don't have their own step yet.

The `run_id` in each successful reply is that turn's run, so you can look it up.

The opt-in emergency-check evaluation (`tests/test_emergency_check_live.py`) records one run named
`emergency_check_live_eval`, with `emergencies_caught`, `false_alarms` and `cases` for its 14 test
sentences. Like every test, it writes to a throwaway MLflow database, not the project's
`mlflow.db`, so its result is read from the test output.

## Look at it

With the backend running and at least one chat done, start the MLflow screen from the project
folder:

```powershell
uv run mlflow ui
```

Open http://127.0.0.1:5000 and choose `vetai-chat`.

- The **Runs** table has one row per turn. Sort by `turn_seconds` to find slow turns, or filter by
  a prompt fingerprint to see only runs made with one version of a prompt.
- The **Traces** tab shows each turn's model calls, with their prompts, replies and timings.
- Select two runs and choose **Compare** to see how a prompt or model change affected them.

## Analyse it

This prints how long turns take for each model and kind of reply, and which steps fail and why.
Run it from the project folder with `uv run python`:

```python
import mlflow

mlflow.set_tracking_uri("sqlite:///mlflow.db")
turns = mlflow.search_runs(
    experiment_names=["vetai-chat"],
    filter_string="attributes.run_name = 'chat_turn'",
)
print(len(turns), "chat turns")
print(turns.groupby(["params.model", "tags.reply_kind"])["metrics.turn_seconds"]
      .describe()[["count", "50%", "max"]].round(1))
print(turns.groupby(["tags.failed_stage", "tags.failure_reason"]).size())
```

On the runs recorded while building this project, it showed gpt-oss:20b answering questions in
0.9 seconds (median) and 6.9 seconds at worst. It also showed that every failure so far was the
model's reply not fitting the required shape (`invalid_model_output`), spread across the
follow-up, emergency-check and summary steps.

## Where the data goes

- If `MLFLOW_TRACKING_URI` is set, MLflow uses it. Otherwise the backend saves to `mlflow.db` in
  the folder it was started from. `uv run mlflow ui` reads the same file, so start both from the
  project folder.
- The runs hold what the owner typed: the concern, the answers, the search queries, and the page
  text sent to the model. `mlflow.db` stays on this machine, and git and Docker ignore it. Delete
  it to clear the history.
- The tests and the browser test's backend use a throwaway database, so they never write to the
  project's `mlflow.db`.
- The example Docker image (untested) sets `MLFLOW_TRACKING_URI=sqlite:////home/vetai/mlflow.db`,
  because its user can't write to `/app`. Those runs are lost when the container is removed.

## How the code works

`chat_runs.py` has two functions:

- `start_tracking()` runs once when the server starts (from `backend.app.create_runtime_app`). It
  picks the database, chooses the `vetai-chat` experiment, and turns on
  `mlflow.langchain.autolog()`, which traces every LangChain call from then on.
- `run_tracked_turn(turn, chains, searcher, run_params)` runs one turn inside its own run and
  returns the reply with the run's ID. The chat endpoint in `backend/app.py` calls it for every
  message.

**Recording never changes the reply.** This is the usual rule for tracking: lose the record rather
than change what the app does.

- If MLflow can't open a run (for example, the database file is read-only), the turn is answered
  without one. The error goes to the server log and the reply's `run_id` is `null`. That turn isn't
  traced either: with no run of its own, MLflow would file its trace under another turn's run.
- Any later MLflow write that fails, such as when the database is briefly locked, is logged and
  skipped. The owner still gets the reply they would have got. The run may then be missing a value.

**Problems found in real use, and how the code handles them:**

| Problem | What the code does |
| --- | --- |
| MLflow linked a trace to the latest open run in any thread, so two overlapping turns shared one run | Each turn's trace is started with its own `run_id` |
| With background saving, some traces were written as files under `./mlruns` instead of into `mlflow.db` | Each trace is saved before the turn returns |
| MLflow's pool of 15 shared database connections ran out when about 48 turns arrived at once | A new connection is opened for each use (`NullPool`) |
| The MLflow screen's Delete button only moves an experiment to a bin, and MLflow then refuses to use it | `start_tracking()` brings `vetai-chat` back when the server starts |
| When the project folder's path had a space or `&`, MLflow's default location encoded it, and runs landed in a differently named folder | With no `MLFLOW_TRACKING_URI` set, the backend uses the relative path `sqlite:///mlflow.db` |

## Not done yet

- a trace step for the web search and page downloads;
- timings for each step as run metrics (they are already visible in each trace);
- a run ID in error replies;
- recording the real-model test chats in MLflow (they are saved as JSON files today);
- scoring summaries with a second model ("LLM as a judge") and storing the scores on each run.
