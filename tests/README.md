# Tests

```powershell
uv run pytest            # about 200 tests, under 30 seconds
uv run ruff check .      # lint
```

The ordinary tests need no Ollama, no internet and no screen. They swap in stand-ins, defined in
`conftest.py`:

- `FakeChains` replaces the four model steps. Each test scripts exactly what the "model" replies,
  and the fake records which steps were called, so a test can check that nothing ran after an
  emergency.
- `FakeSearcher` replaces the web search with fixed pages, or with a chosen failure.

Any MLflow runs the tests make go to a throwaway database, never the project's `mlflow.db`. The
top of `conftest.py` sets `MLFLOW_TRACKING_URI` before anything imports `backend.app`, because
importing it starts tracking.

The example conversations these tests check, with their case IDs (S1, A6, J3 and so on), are in
[`documentation/test-cases.md`](../documentation/test-cases.md).

## What each file checks

**The conversation**

| File | What it checks |
| --- | --- |
| `test_workflow.py` | The order of steps; both emergency checks on every message; the three standard questions; the follow-up count and limit; the repeat rule; that a failed step stops the steps after it |
| `test_questions.py` | The three standard questions, and which one comes next |
| `test_safeguards.py` | Each emergency phrase rule, and ordinary sentences that must not match, such as "maybe a week" |
| `test_scan_scope.py` | The phrase list reads only the owner's words, never the app's questions, search results or model output |
| `test_search.py` | Query checks, approved-site checks, redirects, duplicates, partial failures, the retry waits and 20-second limit, and "no results" versus "no usable pages" |
| `test_model_output.py` | The shape each model step must reply in, the outcome rules, and citations to pages that weren't read |
| `test_model_adapter.py` | Building the model from settings, and the two gpt-oss reply quirks the adapter handles |
| `test_j3_regression.py` | Rules in the prompt files that past real chats showed were needed, such as the normal-or-worrying search query and general guidance when no pages are found |

**The API and the app**

| File | What it checks |
| --- | --- |
| `test_api.py` | Successful question and summary replies, a `503`, `422` replies, and serving the built browser page |
| `test_error_contracts.py` | The main `503` and `500` replies over HTTP (malformed model replies, a timeout, an unexpected search error, a made-up page ID, a crash), that no model step is retried, and that a failed search still gives a summary with a notice |
| `test_mlflow_tracking.py` | One run per message with its parameters, timing and reply kind; failure tags; traces; overlapping turns; MLflow failures that must not change the reply; restoring a deleted experiment; 48 turns at once; the database location |
| `test_runtime_app.py`, `test_settings.py` | Starting the real app from settings, the model and prompt versions recorded on each run, and the environment variables |
| `test_launch.py` | The README's command for the desktop window finds the installed package |

**The desktop window**

| File | What it checks |
| --- | --- |
| `test_frontend_state.py` | The window's chat state: the form, accepted history versus the answer being typed, and the chat ending |
| `test_frontend_window.py` | The window itself, drawn off-screen: bubbles, "Thinking…", **Try again** (including after a failed first message), summaries with links, refusing over-long text, **New concern** |
| `test_frontend_api.py` | Reading each kind of reply, and showing the backend's message for `422` and `503` |
| `test_desktop_backend_contract.py` | The desktop's real requests sent to the real backend code, so the two can't drift apart |

**The browser page**

`src/frontend/public/e2e/full-process.spec.js` builds the page, starts a real backend with the
stand-in model and fake search, and drives Microsoft Edge through six whole chats: a "possible
problem" summary, a "nothing flagged" summary, a failed search that still gives a summary with a
notice, a phrase-list emergency, a misspelled emergency caught by the model check, and a failed
step followed by **Try again**. It runs separately, because it needs Node:

```powershell
cd src/frontend/public
npm run test:e2e
```

## Tests that use the real model or the internet

These are skipped unless switched on with an environment variable, because they depend on Ollama,
a network connection, or outside websites.

| File | Switch | What it checks |
| --- | --- | --- |
| `test_ollama_smoke.py` | `VETAI_RUN_OLLAMA_SMOKE=1` | The real model returns a valid reply for each model step, using fake pages |
| `test_emergency_check_live.py` | `VETAI_RUN_EMERGENCY_CHECK_LIVE=1` | The real emergency check on 7 clear emergencies and 7 ordinary statements: all 7 caught and no false alarms. Records the result in MLflow |
| `test_approved_source_smoke.py` | `VETAI_RUN_LIVE_SEARCH_SMOKE=1` | Downloads one known approved page through the real search code |
| `test_live_customer_journeys.py` | `VETAI_RUN_LIVE_E2E=1` | Whole chats (J1 to J4) with the real model and live search. Saves a JSON record of each under `artifacts/live-journeys/` for a person to review |

For example:

```powershell
$env:VETAI_RUN_OLLAMA_SMOKE = "1"
uv run pytest tests/test_ollama_smoke.py -v -s
```

These all build the model with the same settings as the running app, including the gpt-oss
settings. Set `VETAI_OLLAMA_MODEL` to try another model. `live_journey_checks.py` holds the rules
the J1 to J4 chats are checked against, and `test_live_journey_checks.py` tests those rules
without the model.
