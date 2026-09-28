# Backend

The backend is a FastAPI app with one chat endpoint, `POST /v1/chat`. Each time the owner sends
a message, the browser page or desktop window posts the whole chat so far. The backend checks it,
works out what comes next, and replies with one of three things:

- a **question** for the owner to answer;
- an **emergency notice**, which ends the chat;
- an **assessment**, the final summary with sources, which also ends the chat.

The backend keeps nothing between messages. Every message is recorded as one MLflow run by the
separate [`../mlflow_tracking/`](../mlflow_tracking/README.md) package.

| File | What it does |
| --- | --- |
| `app.py` | Builds the FastAPI app, wires in the model and search, and serves the built browser page |
| `workflow.py` | `run_turn`: decides what happens next for one message, and checks the summary's citations |
| `safeguards.py` | The fixed list of emergency warning phrases. Imports nothing else from the project |
| `questions.py` | The three standard questions |
| `model.py` | The four LangChain chains, all using one Ollama model, and prompt-file loading |
| `search.py` | Checks the search queries, searches the web, and downloads and trims approved pages |
| `approved_sources.py` | Loads the approved-site list and checks whether a web address is on it |
| `schemas.py` | The shape and size limits of every request, model reply, and response (Pydantic) |
| `error_handling.py` | Turns failures into the fixed `422`, `503` and `500` replies |
| `settings.py` | Reads the model name, Ollama address, timeouts and search region from the environment |

It also reads two things from outside this folder: the prompt files in
[`../../prompts/`](../../prompts/README.md) and the approved-site list in
[`../../config/approved_sources.toml`](../../config/approved_sources.toml).

## How one message is handled

The diagram in the [root README](../../README.md#what-happens-in-a-chat) shows this flow.
`run_turn` in `workflow.py` goes through these steps in order. It stops at the first step that
produces a reply.

1. **Check the chat history.** Reject it with a `422` if it is out of order (see
   [Working out where the chat is](#working-out-where-the-chat-is)).
2. **Emergency phrases.** `safeguards.find_emergency` looks for fixed warning phrases in the
   owner's own words: the concern and every answer. It never reads the app's questions, search
   results, or model output. A match returns the emergency notice.
3. **Model emergency check.** The emergency-check chain answers one yes-or-no question: could the
   signs the owner reported need an emergency vet now? It catches what the phrase list misses,
   such as a pet's name ("Max collapsed"), a misspelling, or a sign the list doesn't name. It is
   told to say yes when unsure. Yes returns the same emergency notice. If this step fails, the
   turn fails with a `503`; it is never treated as "no emergency".
4. **Standard questions.** If fewer than three have been answered, return the next one from
   `questions.py`.
5. **Follow-up questions.** Ask the follow-up chain for the next question, unless three
   follow-ups have already been answered.
6. **Search queries.** The query chain writes one to three short search queries.
7. **Web search.** `search.py` searches the approved sites and keeps up to four usable pages.
8. **Summary.** The summary chain writes the assessment from those pages. `_ground_assessment`
   then checks every citation and builds the final reply. If the search found no usable pages,
   the summary is written from general guidance alone and the reply carries a notice saying so.

Steps 2 and 3 run on every message, so the emergency checks see the first concern and every
answer, including the last one before search. Either check can raise an emergency; nothing later
can cancel one. Both lead to the same fixed notice, so the model never writes its wording.

## Working out where the chat is

Because nothing is stored between messages, the backend counts the question-and-answer pairs in
the history it is sent:

| Pairs already answered | What happens next |
| --- | --- |
| 0 to 2 | The next standard question |
| 3 | The first follow-up question. The model must ask one |
| 4 or 5 | The model asks another follow-up, or says it has enough and search starts |
| 6 | Search starts. The model is not asked, so it can't add a fourth follow-up |

The history must alternate app question then owner answer, end with an owner answer, and hold at
most 12 messages. The first three questions must match the standard questions word for word.
Nothing else is checked, so a custom client could change the follow-up questions. That is a known
limit of keeping no memory on the server.

If the model repeats a question that was already asked, the backend treats it as "I have enough"
and starts search. A repeat is the same words ignoring capitals, or two questions that both ask
about the pet's age ("age" or "how old"), which the model tended to ask twice in different words. On the first follow-up that isn't allowed,
so the turn fails with a `503` instead.

## The four model steps

`model.py` builds one `ChatOllama` model and four chains from it. The workflow calls them as:

```python
chains.check_for_emergency(turn)               # -> EmergencyCheck(emergency: bool)
chains.propose_adaptive_question(turn, mode)   # -> AdaptiveDecision: a question, or ready
chains.generate_search_plan(turn)              # -> SearchPlan: 1 to 3 queries
chains.synthesise_assessment(turn, evidence)   # -> AssessmentDraft
```

Each chain is `prompt | model.with_structured_output(schema)`, so the model must reply in the
shape of a Pydantic class from `schemas.py`. A reply that doesn't fit is rejected and never shown.
`mode` tells the follow-up chain whether it may say it has enough: `question_required` for the
first follow-up, `question_or_ready` after that. For gpt-oss each chain has one more step, explained
in [How gpt-oss and llama3 behave differently](#how-gpt-oss-and-llama3-behave-differently).

The model's context window (how much text it reads at once) is set to 16,384 tokens
(`CONTEXT_WINDOW_TOKENS`). Ollama's default of about 2,000 tokens silently dropped the start of
long summary prompts, which removed the rules and the owner's report and caused empty or made-up
replies. The longest summary prompt is about 12,000 tokens.

**What the summary may and may not write.** The summary chain chooses the outcome,
`possible_problem` or `nothing_flagged`, and writes:

- points a vet may consider (0 to 3, only for `possible_problem`);
- suggested actions (1 to 4);
- questions for the vet (1 to 3).

When pages were found, every item cites 1 to 4 of them by ID (`S1`, `S2` and so on). The model may
also add widely accepted general vet guidance that fits the owner's report and doesn't contradict
the pages, still citing the most relevant page. When no pages were found, every item has an empty
citation list and the reply's `search_notice` field says "The source search did not work, so this
result is based on general guidance and has no linked sources." The prompt tells the model to choose
`possible_problem` only when the owner reported something abnormal: a web page about an illness
is not enough. The model does not write the recap of what the owner said, the outcome wording, the
disclaimer, or any links. The workflow adds all of those, and builds the source list from the page
IDs that were actually cited.

**Prompt versions.** Each prompt file has `<!-- system -->` and `<!-- human -->` sections.
`PromptFile.load` splits them and takes a SHA-256 fingerprint of the file, and every MLflow run
records the four fingerprints. So you can tell which prompt text produced which result.

## How gpt-oss and llama3 behave differently

The same four chains behave differently on the two models tried, so the backend treats gpt-oss
differently. For llama3 and any other model, each chain is the plain LangChain form:
`prompt | model.with_structured_output(schema)`. For gpt-oss it needs an extra reading step.

MLflow traced every model call while this was worked out, so the table below comes from the
traces in `mlflow.db` (25 to 27 September 2026) and from the tests that pin each fix.

| Behaviour | llama3 8B | gpt-oss:20b | What the code does |
| --- | --- | --- | --- |
| How a structured reply is requested | `json_schema`: Ollama restricts the model's output to the schema. All 13 recorded calls worked | With `json_schema`, its one recorded call (25 Sep, 11:46 UTC) returned a completely empty reply | `settings.py` uses `function_calling` for any `gpt-oss:*` model: the schema is sent as a tool, and the model answers with a tool call (`tests/test_settings.py`) |
| Answering with a tool call | Not used | 54 of 67 recorded calls were proper tool calls. 13 had no tool call: 10 held valid JSON in the message text instead, and 3 held nothing usable | The chain keeps the raw reply (`include_raw=True`), and a last step, `_parse_function_calling_result`, checks the message text against the same Pydantic class (`tests/test_model_adapter.py`). The 3 unusable replies were rejected with a `503` |
| Field names in the summary | Not seen | Sometimes names each item's text `area`, `action` or `question` instead of `text`. Seen in the real-model test chats, which aren't stored in `mlflow.db` | Only those three names are renamed to `text`, then the reply is checked again. Any other wrong field is still rejected (`tests/test_model_adapter.py`) |
| An empty citation list | Not seen | Wrote it in a form Ollama's reply reader rejected | When no pages were found, the prompt asks for the placeholder ID `"none"`, and the code drops it |
| Thinking before answering | Doesn't think first | Its thinking shares the 900-token output limit with its answer, and could use all of it | Reasoning effort is set to "low". Switching it off isn't supported |
| Keeping to the question limit | Asked a fourth follow-up even though the prompt said not to | Not relied on | The code counts follow-ups and stops calling the model after three, for any model |

**What the extra reading step saves.** The 10 recovered replies were 6 emergency checks, 2
summaries, 1 follow-up question and 1 set of search queries. Without the step, each would have
been a `503`. A failed emergency check fails the whole turn, so the 56 recorded turns would have
had up to 15 failures instead of 5. The step reads a reply that has already arrived, so it costs
no extra model call. It never changes what the model said: it only takes the JSON from the message
text, or renames one of three known field names.

**What isn't known.**

- Why `json_schema` gives gpt-oss an empty reply. Only the symptom was recorded, from one call. A
  newer Ollama may fix it. To re-test, have `structured_output_method` in `settings.py` return
  `json_schema` for gpt-oss, then run `VETAI_RUN_OLLAMA_SMOKE=1 uv run pytest
  tests/test_ollama_smoke.py -v -s`. If it passes, the extra reading step could go.
- Whether llama3 would show the same habits under more use. Its 13 recorded calls all came from
  one morning, with an older summary prompt.

**Count it yourself.** This prints how each recorded chain call was read. Run it from the project
folder with `uv run python`:

```python
from collections import Counter

import mlflow

mlflow.set_tracking_uri("sqlite:///mlflow.db")
experiment = mlflow.get_experiment_by_name("vetai-chat")
runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id], output_format="list")
model_of = {run.info.run_id: run.data.params["model"] for run in runs}
counts = Counter()
for trace in mlflow.search_traces(experiment_ids=[experiment.experiment_id], return_type="list"):
    model = model_of[trace.info.request_metadata["mlflow.sourceRun"]]
    spans = trace.data.spans
    for chain in (s for s in spans if s.name == "RunnableSequence"):
        steps = {s.name: s for s in spans if s.parent_id == chain.span_id}
        if "ChatPromptTemplate" not in steps:
            continue  # a step inside a chain, not a whole chain call
        if "RunnableLambda" not in steps:  # no custom reading step: json_schema or plain tool call
            form = "read by LangChain, " + chain.status.status_code
        elif steps["RunnableLambda"].inputs["parsed"] is not None:
            form = "tool call, read by LangChain"
        elif steps["RunnableLambda"].status.status_code == "OK":
            form = "no tool call, JSON in the text, recovered"
        else:
            form = "no tool call, nothing usable, rejected"
        counts[(model, form)] += 1
for (model, form), n in sorted(counts.items()):
    print(f"{n:4d}  {model:15s} {form}")
```

On the recorded runs it prints the 54, 10 and 3 above for gpt-oss, and 13 successful llama3
calls. It also shows the 6 gpt-oss calls made on 25 September, before the extra step existed: the
1 failed `json_schema` call, and 5 tool calls that LangChain read without it.

## Web search

The model never sees the search engine, and the search engine never sees the chat.

1. **Check the queries.** `query_is_safe` rejects any query containing a web address, an email
   address, or something that looks like a phone number, before anything is sent.
2. **Search.** Each query is sent to DuckDuckGo (through the `ddgs` package) with a `site:`
   filter for the six approved sites, the configured region (UK by default), and moderate safe
   search. At most three results are kept per query.
3. **Keep partial results, and retry a total failure.** If one query fails but another returns
   results, those results are kept. If every query fails, the same queries are sent again after
   1, then 2, then 4 seconds (up to four attempts). A new attempt starts only if, judging by how
   long the last one took, it should finish within 20 seconds of search time. That leaves room for
   the summary inside the screens' 65-second limit. This is
   the only automatic retry in the backend.
4. **Check each result.** A result is kept only if it uses HTTPS and its host is an approved site
   or a subdomain of one. `aspca.org.example.com` does not count as `aspca.org`. Duplicate
   addresses are dropped. The search engine's `site:` filter is not trusted on its own.
5. **Download the page.** `HttpPageFetcher` checks the site list again before every redirect,
   follows at most three, accepts only HTML or text under 500,000 bytes, removes scripts, styles,
   navigation and forms, and keeps the first 4,000 characters. A page that fails is skipped, and so
   is a result with a title over 300 characters.
6. **Number the pages.** The first four usable pages become `S1` to `S4`. Page text is treated as
   untrusted: instructions inside a page can't change the rules.

Only the short generated queries leave the machine. Search services and the approved sites can
still see those queries, the pages requested, and the machine's public IP address.
[`../../documentation/approved-sources.md`](../../documentation/approved-sources.md) explains why
each site was chosen.

## Limits

| What | Limit | Set in |
| --- | ---: | --- |
| Standard questions | exactly 3 | `questions.py` |
| Follow-up questions | at least 1, at most 3 | `workflow.py`, `schemas.py` |
| Chat history | at most 12 messages (6 question-and-answer pairs) | `schemas.py` |
| Concern or answer | 1,000 characters | `schemas.py` |
| A follow-up question | 500 characters | `schemas.py` |
| Search queries | 1 to 3, each 3 to 120 characters | `schemas.py` |
| Search results kept per query | 3 | `search.py` |
| Search attempts | up to 4, after waits of 1, 2 and 4 seconds, only while every query fails, and only if expected to finish within 20 seconds | `search.py` |
| Redirects, page size, text kept per page | 3, 500,000 bytes, 4,000 characters | `search.py` |
| Pages sent to the summary | 4 | `search.py` |
| Page title | 300 characters | `schemas.py` |
| Model output per call | 900 tokens | `model.py` |
| Model context window | 16,384 tokens | `model.py` |
| Model call timeout | 60 seconds (`VETAI_OLLAMA_TIMEOUT_SECONDS`) | `settings.py` |
| Each search call and each page download | 12 seconds (`VETAI_SEARCH_TIMEOUT_SECONDS`) | `settings.py` |

## When something fails

This is the one place the error behaviour is written down.

**The rules:**

- Nothing is retried automatically, except a completely failed web search (see
  [Web search](#web-search)).
- A failed model step has no fallback answer. A broken model reply is never shown, and the model is
  never asked to "try again another way".
- A failed web search is the exception: the summary goes ahead on general guidance, with no
  sources and a notice saying the search didn't work. This covers only search-service outages. An
  unsafe search query (a model fault) or an unexpected error in the search code (a bug) still stops
  the turn with a `503`.
- The owner sees one of three replies: `422` (fix the request), `503` (a step failed, try again),
  or `500` (an unexpected bug, same wording as `503`).
- Which step failed, and why, goes to the server log and onto the turn's MLflow run as the
  `failed_stage` and `failure_reason` tags. It is never sent to the owner.
- Recording in MLflow never changes the reply. If MLflow fails, the owner still gets the answer
  they would have got.

**The replies:**

A `422`, when the request needs fixing:

```json
{"error": "Please correct the request and try again.",
 "issues": [{"field": "history", "message": "Correct the chat history and try again."}]}
```

A `503` or `500`, when a step failed:

```json
{"error": "The assistant could not complete this response. Please try again or contact a veterinarian if concerned.",
 "run_id": null}
```

**Every case:**

| What happened | Recorded as (stage: reason) | Reply |
| --- | --- | --- |
| Missing or unknown field, species not dog or cat, blank concern or answer, or over 1,000 characters | not recorded: FastAPI rejects it before the turn starts | `422`, naming the field |
| History over 12 messages | not recorded: FastAPI rejects it before the turn starts | `422` on `history` |
| History out of order, ends on a question, or the first three questions don't match the standard ones | failure reason `InvalidTurnRequest` | `422` on `history` |
| An emergency phrase matched | not a failure | Emergency notice; chat ends |
| The model emergency check said yes | not a failure | Emergency notice; chat ends |
| A model call timed out | *step*: `timeout` | `503` |
| Ollama couldn't be reached | *step*: `connection` | `503` |
| The model's reply didn't fit the required shape | *step*: `invalid_model_output` | `503` |
| Any other model error | *step*: `model_call_failed` | `503` |
| First follow-up: the model said it had enough, or repeated a question | `adaptive_question`: `question_required` | `503` |
| A search query contained a web address, email or phone number | `approved_source_search`: `unsafe_search_query` | `503` |
| Every search attempt failed | not a failure: a server-log warning (`search_failed`) | Summary without sources, with the search notice |
| Search worked but found nothing | not a failure: a server-log warning (`no_search_results`) | Summary without sources, with the search notice |
| Results were found, but no page passed the checks | not a failure: a server-log warning (`insufficient_evidence`) | Summary without sources, with the search notice |
| Any other unexpected error inside the search code | `approved_source_search`: `search_failed` | `503`, because it is a bug, not a service outage |
| The summary cited a page ID that wasn't retrieved | `evidence_synthesis`: `ungrounded_synthesis` | `503` |
| Pages were found, but a summary item cited none | `evidence_synthesis`: `ungrounded_synthesis` | `503` |
| Any other unexpected error | the error's type | `500` |

*Step* is whichever model step failed: `emergency_check`, `adaptive_question`, `search_query` or
`evidence_synthesis`.

**These are not failures; the turn carries on:**

- one search query fails but another returns results;
- a result is off the list, not HTTPS, redirects off the list, fails to download, or has a title
  over 300 characters: it is skipped;
- three follow-up questions have been answered: search starts without asking the model;
- a later follow-up repeats an earlier question: search starts;
- the web search fails or finds nothing usable: the summary goes ahead without sources.

**Known issue:** a history whose standard questions don't match gets the message "Chat history
messages must alternate from the assistant and owner", which describes a different problem.
`error_handling.py` picks the message by searching the error's text.

**Timing:** a model call gives up after 60 seconds, and each search call and page download after
12 seconds, and search retries stop within 20 seconds. Both screens stop waiting after 65
seconds. The backend does not notice when a screen
stops waiting, so it finishes the turn anyway, and **Try again** starts it from the beginning.
What each screen shows for each reply is in
[`../frontend/README.md`](../frontend/README.md).

## Endpoints

- `GET /health` returns `{"status": "ok"}` without calling the model or search.
- `POST /v1/chat` handles one message. A successful reply includes `run_id`, the turn's MLflow run.
  `503` and `500` replies have `"run_id": null` for now; `422` replies have no `run_id`.
- `GET /docs` is FastAPI's generated API page.
- `/` serves the built browser page from `../frontend/public/dist/`, if it has been built. It is
  added last so it can't hide the routes above. Serving the page and the API from one address
  means no cross-origin (CORS) setup is needed.

## Tests

| Test file | What it checks |
| --- | --- |
| `tests/test_workflow.py` | Step order, both emergency checks on every message, the question counts, the repeat rule, and that a failed step stops later steps |
| `tests/test_safeguards.py` | Each emergency phrase rule, and ordinary sentences that must not match |
| `tests/test_search.py` | Query checks, approved-site checks, redirects, duplicates, partial failures, the retry waits and 20-second limit, and "no results" versus "no usable pages" |
| `tests/test_model_output.py` | Reply shapes, outcome rules, and unknown or missing page IDs |
| `tests/test_api.py` | Successful replies and `422` replies |
| `tests/test_error_contracts.py` | The `503` and `500` replies over HTTP: malformed follow-up and summary replies, a timeout, an unexpected search error, a made-up page ID, and an unexpected crash. Also that no model step is retried, and that a failed search still gives a summary with the notice. The remaining failure reasons are tested one layer down, in `tests/test_workflow.py` |
| `tests/test_mlflow_tracking.py` | One MLflow run per message, failure tags, traces, and that MLflow failures don't change replies |

These use a stand-in model and fake search results, so they need no Ollama and no network.
[`../../tests/README.md`](../../tests/README.md) lists every test file and the opt-in tests that
use the real model.
