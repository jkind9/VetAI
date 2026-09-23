# VetAI project review (2026-09-23)

A read-only review of this repository, written for the owner and for anyone working on the code
next. It covers:

- how readable the code is;
- how well the project answers the technical-test brief
  ([`e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf`](e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf));
- which backend behaviour needs fixing.

**What was reviewed:** commit `5b3dd0b` plus the uncommitted working tree on 2026-09-23. Line
numbers refer to that state, so later commits may shift them.

**How claims were checked.** Every failure below was reproduced, except where it says "found by
reading". The checks were:

- the test suite and ruff;
- the emergency phrase matcher, run on sample sentences;
- the desktop client's real requests, sent to an in-memory copy of the backend;
- calls to the local Ollama model;
- fetches of two approved web pages.

> **Reviewer comment — Agree with the evidence-first method.** The current recheck reran the full
> offline suite, Ruff, all seven matcher samples, the local Ollama context check, Git history and
> remote-head checks, and static client/backend contract inspection. Exact historical page-character
> and prompt-token counts remain contemporaneous measurements rather than stable fixtures.

Terms used below:

- **standard questions**: the three fixed questions every chat starts with (how long, has it
  happened before, constant or on and off).
- **adaptive questions**: the one to three follow-up questions the model chooses.
- **synthesis**: the final model step that turns retrieved web pages into the owner's
  assessment.
- **phrase matcher**: the plain-Python list of emergency phrases in `safeguards.py`. It checks the
  owner's own words before any model call.

### Reviewer comment legend

- **Agree** — verified from the brief, repository, Git history, a reproducer, or the current test
  suite. Include it in the execution plan when work remains.
- **Partly agree** — the underlying concern is valid, but the proposed interpretation or fix needs
  another design decision. These items are collected for later review rather than execution.
- **Disagree** — the repository or document does not support the claim. Do not put it in the
  execution plan.

Reviewer comments below were added after checking the current working tree. They distinguish a
problem that existed in the reviewed snapshot from one that remains open now.

## Summary

The backend is small: 1,271 lines in 10 files. Most of it reads top to bottom. At review time the
offline tests passed (112 passed, 12 live tests skipped) and `ruff check` was clean. Five problems
matter most:

> **Reviewer comment — Agree for the reviewed snapshot.** The size/readability characterization is
> fair. After the latest parallel MLflow update, the current uncommitted tree is 149 passed and 12
> skipped, and Ruff is clean.

1. MLflow is missing, and it is one of the three things the brief asks for.
   > **Reviewer comment — Agree for the reviewed snapshot.** The brief explicitly requires MLflow
   > and asks for prompt, response, and timing tracking. A new uncommitted implementation now exists
   > in `src/mlflow_tracking/`, but its own README still lists missing search/fetch spans, error run
   > IDs, live-journey integration, and analysis, so the requirement is not finished or pushed yet.
2. The desktop client that the README tells people to run first can't complete a chat with the
   current backend.
   > **Reviewer comment — Agree for the reviewed snapshot.** Both contract mismatches were
   > confirmed. They are fixed in the current working tree, including a real desktop-to-backend
   > contract test, but the fix is still uncommitted and unpushed.
3. At review time, GitHub held only the first commit ("VetAI_takehome"). Local `main` was 16
   commits ahead, and the browser client wasn't committed.
   > **Reviewer comment — Agree.** The remote `main` still points to the first commit. Local `main`
   > is now 20 commits ahead and the browser client remains untracked.
4. The phrase matcher misfires on ordinary answers and misses some real emergencies.
   > **Reviewer comment — Agree.** Every example in problem 1 still reproduces.
5. The synthesis step can silently lose its safety rules.
   > **Reviewer comment — Agree.** `num_ctx` is unset. The installed model advertises an
   > 8,192-token context, while the current Ollama session runs with 4,096.

## Broken at the time of review

- **The desktop client can't talk to the backend.**
  > **Reviewer comment — Agree for the reviewed snapshot; fixed locally now.** Keep the item as
  > historical evidence of the contract drift, but close it only after the current fix is committed
  > and pushed.
  - Its form still sends `duration`, `previous_occurrence` and `pattern` with the intake
    ([`src/frontend/local/app.py:157-164`](src/frontend/local/app.py#L157-L164)). The backend
    rejects unknown intake fields, so the first request gets a 422 and no question ever appears.
    > **Reviewer comment — Agree.** The reviewed version sent fields forbidden by `Intake`.
  - Even past that, it only accepts a reply kind called `"summary"`
    ([`src/frontend/local/api_client.py:41`](src/frontend/local/api_client.py#L41)). The backend
    now sends `"assessment"`, so the final result would show as "The assistant could not complete
    this response".
    > **Reviewer comment — Agree.** The reviewed parser and the backend used different terminal
    > reply kinds.
  - Its tests still assert `"summary"`
    ([`tests/test_frontend_state.py:58`](tests/test_frontend_state.py#L58)) and never send the
    desktop's request to the real backend, which is why they pass.
    > **Reviewer comment — Agree.** The old tests covered each side separately, not their shared
    > wire contract. The new uncommitted contract test addresses this exact gap.
- **The browser client can't retry a failed first request** (found by reading).
  > **Reviewer comment — Agree; still open.** Existing browser E2E coverage retries a later model
  > failure, not a failed initial request.
  - After the first request fails (for example, the backend is down), `send()` in
    [`src/frontend/public/src/App.svelte:24-40`](src/frontend/public/src/App.svelte#L24-L40)
    treats the chat as started and asks for an answer. The answer box is hidden until a question
    arrives, so "Try again" only shows "Enter an answer."
    > **Reviewer comment — Agree.** `started` becomes true as soon as intake is stored, before the
    > first question is accepted.
  - The owner has to reload the page. Keying that branch on "no question yet" rather than "intake
    set" would fix it.
    > **Reviewer comment — Agree.** Track whether the first question has been accepted, or treat a
    > chat with no accepted question/history as an intake submission on retry.

## Against the brief

| The brief asks for | State | Notes | Reviewer comment |
|---|---|---|---|
| A LangChain chain | Done | Three chains in [`model.py`](src/backend/model.py), each prompt in its own markdown file under [`prompts/`](prompts). Easy to explain. | **Agree.** This is one of the clearest parts of the submission. |
| MLflow tracking of prompts, responses and timing | Missing in the reviewed snapshot; implementation now in progress | The reviewed state had no dependency or application code. A new uncommitted `src/mlflow_tracking/` package now records one run per turn, LangChain traces, prompt hashes, successful response run IDs, and total timing. Search/fetch spans, failed-response run IDs, live-journey integration, and analysis remain open. | **Agree with the original finding; update the current status.** Finish and push the implementation, reusing the live-journey event data rather than keeping a second tracking model. |
| Clear structure | Yes | One backend file per job. | **Agree.** The package is small and responsibilities are mostly easy to locate. |
| A simple README | No | It's 196 lines, and it argues the design before saying what the project is. The install and run commands appear three times (Quickstart, Setup, Run locally). The first run path is the broken desktop client. | **Partly agree.** It does satisfy the required setup/run documentation, but it is not simple and the duplicated commands create drift. The desktop path is fixed locally but not in GitHub. |
| Chat UI ("won't be judged") | Over-built | Two clients: about 1,100 lines plus Playwright tests, against no MLflow code. | **Agree as a prioritisation judgment.** Two presentations are difficult to justify while a named requirement is absent. |

The project does much more than the brief asked: web search limited to approved vet sites,
emergency routing, and two clients. That extra scope came at the cost of the one tool the brief
names besides LangChain.

> **Reviewer comment — Partly agree.** The prioritisation evidence is strong, but literal causation
> cannot be proved from the repository alone. The actionable point is to stop adding scope until
> MLflow and the existing safety defects are complete.

The documentation is 1,325 lines of markdown, more than the backend code. The error table appears
twice, in [`documentation/failure-handling.md`](documentation/failure-handling.md) and
[`src/backend/README.md`](src/backend/README.md), and both already disagree with the code:

> **Reviewer comment — Agree.** Exact counts depend on the snapshot, but the documentation volume,
> duplicated contract table, and resulting drift are real.

- [`failure-handling.md:51`](documentation/failure-handling.md#L51) describes using a search
  snippet when a page fetch fails. No such code exists.
  > **Reviewer comment — Disagree.** The document says a snippet may be used only if an adapter
  > explicitly marks it as evidence. It does not say the current adapter does so. The sentence is
  > speculative and could be removed, but it is not the claimed code/document mismatch.
- [`failure-handling.md:98`](documentation/failure-handling.md#L98) says the final turn gets a
  longer client timeout. Both clients use 65 seconds for every turn.
  > **Reviewer comment — Agree.** The documentation promises behavior neither client implements.
- The backend README says an over-long history raises `InvalidTurnRequest`. Pydantic rejects it
  first.
  > **Reviewer comment — Agree.** This also leaves the error handler's "at most" string branch
  > unreachable.

## Backend problems

### 1. The phrase matcher misfires on ordinary sentences

Run on these sentences:

| Owner writes | Result |
|---|---|
| "I can't remember, maybe a week" | Emergency: `wee` matches inside "week" |
| "Unable to say exactly, a few weeks" | Emergency |
| "Her heart rate went up after her new medication" | Emergency: `ate` matches inside "rate" |
| "She's collapsed in the garden" | No match |
| "He isn't breathing" | No match |
| "Max collapsed on the kitchen floor" | No match |
| "My dog's passed out" | No match |

> **Reviewer comment — Agree.** All seven inputs were rerun against the current matcher and still
> produce the results shown here.

The first sentence is a likely answer to the first standard question, and it ends the chat with
an emergency notice. The causes:

- Two word groups are missing a `\b` word boundary
  ([`safeguards.py:113`](src/backend/safeguards.py#L113),
  [`safeguards.py:123`](src/backend/safeguards.py#L123)).
  > **Reviewer comment — Agree.** This permits `ate` inside `rate` and `wee` inside `week`.
- "she's", "he's" and "dog's" aren't in `PET_WORDS`, and pet names can't be
  ([`safeguards.py:52`](src/backend/safeguards.py#L52)).
  > **Reviewer comment — Agree.** `_WORD` retains apostrophes, so possessives do not match the
  > existing subject vocabulary; arbitrary pet names cannot match it at all.
- Nothing matches "isn't breathing" ([`safeguards.py:91`](src/backend/safeguards.py#L91)).
  > **Reviewer comment — Agree.** The contraction is absent from the breathing expressions.

**Fix:**

- Add the boundaries.
  > **Reviewer comment — Agree.** Add regression tests before changing the expressions.
- Strip a trailing `'s` before the pet-word check.
  > **Reviewer comment — Agree.** This narrowly fixes pronoun and common-noun possessives.
- Add `isn't|wasn't` to the breathing pattern.
  > **Reviewer comment — Agree.** Include typographic-apostrophe variants if owner input may contain
  > them.
- Add each sentence above as a test.
  > **Reviewer comment — Agree.** Preserve both the false-positive and false-negative cases.
- For pet names, consider dropping the pet-subject check on collapse. The README already argues
  that a false alarm is the safer mistake.
  > **Reviewer comment — Partly agree.** This would also match statements such as "I collapsed" or
  > "the fence collapsed." Defer it until acceptable false-positive cases are agreed.

### 2. The synthesis step can silently lose its rules

On the review machine, Ollama runs llama3 with a 4,096-token context window (how much text the
model reads at once; `ollama ps` shows it). The model supports 8,192, but `num_ctx` is never set
([`model.py:99-106`](src/backend/model.py#L99-L106)).

> **Reviewer comment — Agree.** This was reconfirmed: `ollama show` reports 8,192 supported tokens,
> while a live `ollama ps` session reports 4,096 and the constructor does not pass `num_ctx`.

- A real synthesis prompt was built with the project's own code and four excerpts from a PDSA
  page. It was 4,146 tokens.
  > **Reviewer comment — Agree with the finding.** The exact count belongs to that captured page and
  > tokenizer run, but current limits can still construct an over-budget prompt.
- Sent with the backend's settings, Ollama returned success with no error, but the model read only
  2,060 of those tokens.
  > **Reviewer comment — Agree with the demonstrated failure mode.** Silent truncation is more
  > dangerous here than an explicit provider error.
- In a separate test, the same cut removed a 500-token system message, about the size of the
  synthesis rules, and the model stopped following it.
  > **Reviewer comment — Agree.** The application cannot rely on safety instructions outside the
  > effective context.

So when four full-length pages come back, the assessment is written without the "no medicines, no
doses, no reassurance" rules.

> **Reviewer comment — Agree.** A successful provider response is not evidence that the full system
> instruction was available to the model.

**Fix:** pass `num_ctx=8192`, and cut the menus from the page text (item 4).

> **Reviewer comment — Agree, with an additional requirement.** Set `num_ctx=8192`, improve page
> extraction, and add an explicit token budget for the complete synthesis request. Character limits
> alone do not guarantee that prompts fit.

### 3. One failed search query threw away the others

All three queries ran inside one `try`. A first query that found a good page followed by a second
query that hit a rate limit failed the whole search, and the good page was lost.

> **Reviewer comment — Agree for the reviewed snapshot.** The reproduced behavior matches the old
> control flow.

**Update:** fixed after this review by commit `65bb2d3` ("retain partial search results and retry
total outages"). Each query now runs separately, partial results are kept, and the whole plan is
retried once when every query fails.

> **Reviewer comment — Agree and verified.** The current implementation preserves sibling results
> and performs one bounded repeat only after total provider failure.

A related problem is still open:

- A single search result with a title over 300 characters fails the whole turn. The `EvidenceItem`
  is built outside any `try`
  ([`search.py:205-213`](src/backend/search.py#L205-L213) at review time).
  > **Reviewer comment — Agree; still open.** Treat one malformed result as unusable or normalize
  > its title before constructing the validated evidence item.

### 4. The page text sent to the model is mostly site menus

The HTML parser skips `<nav>` but keeps `<header>`, `<footer>` and `<aside>`
([`search.py:54`](src/backend/search.py#L54)).

> **Reviewer comment — Agree.** The current ignored-tag set confirms the structural cause.

- The MSD Veterinary Manual emergencies page gave 1,615 characters, all of it menu.
  > **Reviewer comment — Agree as a contemporaneous live-page measurement.** The exact count may
  > change when the external page changes; the parser defect does not.
- The PDSA "vomiting in dogs" page spent its first 1,100 of 4,000 characters on menus.
  > **Reviewer comment — Agree as a contemporaneous live-page measurement.** Add a deterministic
  > parser fixture so this does not depend solely on live HTML.

**Fix:** skip those tags too, or keep only the text inside `<main>` when a page has one. This also
shrinks the prompt in item 2.

> **Reviewer comment — Agree.** Prefer `<main>` when present, fall back to visible body text, and
> always ignore `header`, `footer`, and `aside`. Cover both paths with local fixtures.

### 5. "Try again" can't fix a bad model answer

The model runs at temperature 0 with a fixed seed, so the same prompt gets the same reply. Two
rules turn a model slip into a dead end:

> **Reviewer comment — Agree.** Exact reproducibility is provider-dependent, but these settings make
> an identical retry very likely to repeat the same forbidden choice.

- the model answers "ready" when it must ask its first adaptive question
  ([`workflow.py:100-101`](src/backend/workflow.py#L100-L101));
  > **Reviewer comment — Agree.** The shared output schema permits a choice this mode rejects.
- the model asks a fourth adaptive question after the limit of three
  ([`workflow.py:88-94`](src/backend/workflow.py#L88-L94)).
  > **Reviewer comment — Agree.** This is the symmetric schema/mode mismatch at the cap.

Both return a 503, and a retry repeats the same reply.

> **Reviewer comment — Agree.** The public failure behavior is safe, but retry is not a meaningful
> recovery mechanism while the prompt and allowed schema remain identical.

**Fix:** give each decision mode (`question_required`, `question_or_ready`, `ready_or_escalate`)
its own reply schema that leaves out the forbidden choice. With `method="json_schema"`, Ollama makes
the reply fit the schema, so the model can't pick that choice, and both error branches go away.

> **Reviewer comment — Agree.** Mode-specific schemas encode the invariant at generation time and
> remove both deterministic retry dead ends. Keep runtime validation as a final boundary.

> **Owner decision (2026-09-23).** A real llama3 chat hit the cap case: the model asked a fourth
> question. The limit of three becomes a plain loop in code, and the model is never offered a
> fourth question. See "Found while fixing", item 1, which also lists the two open choices: the
> final emergency check, and whether one follow-up question stays mandatory.

### 6. The final turn doesn't fit in 65 seconds

The last answer triggers all of this in one request:

> **Reviewer comment — Agree.** The workflow and search implementation confirm this sequential
> critical path.

- the adaptive call;
  > **Reviewer comment — Agree.** A final safety/readiness call still runs at the adaptive cap.
- the search-query chain;
  > **Reviewer comment — Agree.** This is a separate model invocation.
- up to three web searches;
  > **Reviewer comment — Agree.** Planned queries are processed sequentially.
- page fetches one at a time, with a 12-second timeout each;
  > **Reviewer comment — Agree.** Failed candidates can make the total exceed four fetch attempts
  > before four usable evidence items are collected.
- the synthesis call.
  > **Reviewer comment — Agree.** This is another model invocation after retrieval.

Both clients give up at 65 seconds
([`api.js:132`](src/frontend/public/src/lib/api.js#L132),
[`api_client.py:74`](src/frontend/local/api_client.py#L74)). The backend carries on anyway, and
"Try again" starts the searches again.

> **Reviewer comment — Agree.** A synchronous backend turn is not cancelled merely because the
> client stopped waiting, so manual retry can duplicate expensive work.

**Fix:** a longer client timeout (for example 180 seconds) and a cap on total page fetches.

> **Reviewer comment — Partly agree.** A longer final-turn timeout and fetch cap are appropriate,
> but pair them with a server-side total deadline. Derive the client value from those budgets rather
> than copying 180 seconds as another independent constant.

### 7. Wrong error text for a changed standard question

The handler picks its message by searching the exception's text
([`error_handling.py:43-56`](src/backend/error_handling.py#L43-L56)). A changed standard question
comes back as "Chat history messages must alternate from the assistant and owner". The "at most
twelve messages" branch can never run, because Pydantic rejects long histories first.

> **Reviewer comment — Agree.** Both the wrong message and unreachable branch are present.

**Fix:** raise the exception with the owner-facing sentence and delete the lookup.

> **Reviewer comment — Partly agree.** Delete the string inspection, but use structured error codes
> mapped to owner-facing text at the HTTP boundary. Map Pydantic's history-length error there too;
> do not couple workflow exceptions directly to final UI prose.

## Readability: extra layers and unused code

What's worth keeping:

- `run_turn` in [`workflow.py`](src/backend/workflow.py) follows the plan's flow step by step.
  > **Reviewer comment — Agree.** Keep its top-to-bottom state-machine shape.
- [`questions.py`](src/backend/questions.py) and
  [`approved_sources.py`](src/backend/approved_sources.py) are short and clear.
  > **Reviewer comment — Agree.** These are good examples for the rest of the package.
- [`safeguards.py`](src/backend/safeguards.py) explains each rule of thumb next to its code.
  > **Reviewer comment — Agree.** Preserve the rationale comments while fixing the expressions.
- The source-ID rule takes one sentence to explain: the model cites IDs, and the app builds the
  source list.
  > **Reviewer comment — Agree.** This is a simple and auditable grounding boundary.

Lines that are hard to justify:

- **Errors are wrapped two or three times.**
  > **Reviewer comment — Partly agree.** There are several boundary layers, but most outer handlers
  > re-raise `ModelOutputError` unchanged rather than wrapping it again. Simplify only after the
  > injected contracts are made explicit.
  - A model failure is caught in `OllamaChatModel._invoke`
    ([`model.py:154-163`](src/backend/model.py#L154-L163)) and again in `_call_stage`
    ([`workflow.py:169-177`](src/backend/workflow.py#L169-L177)).
    > **Reviewer comment — Partly agree.** `_call_stage` also normalizes failures from non-Ollama
    > injected chain implementations; that purpose should be retained or replaced by a Protocol.
  - A search failure is caught in `search()` and again in `_build_assessment`
    ([`workflow.py:146-153`](src/backend/workflow.py#L146-L153)).
    > **Reviewer comment — Partly agree.** The workflow boundary protects against arbitrary injected
    > searchers. It becomes removable only when the search contract guarantees normalized errors.
  - "No evidence" is checked in both places.
    > **Reviewer comment — Partly agree.** This is duplicate work in production but a cheap defensive
    > invariant with the current `Any` dependency.
  - Every path ends in the same 503 with the same text. The reason codes only feed one log line,
    and `_failure_reason` ([`model.py:181-189`](src/backend/model.py#L181-L189)) guesses them by
    searching exception class names for words like "timeout".
    > **Reviewer comment — Agree about `_failure_reason`; disagree that one public 503 makes the
    > internal reasons unnecessary.** Stable public text and detailed internal observability serve
    > different purposes. Replace heuristic classification with explicit exception mapping.
  - Task 02 kept `_failure_reason` on purpose. It's worth revisiting once MLflow records the real
    exception class for every failed stage.
    > **Reviewer comment — Partly agree.** Revisit the heuristic during MLflow work, but MLflow does
    > not itself remove the need for stable internal reason codes.
- **Model output is validated twice.** LangChain already returns a validated object.
  `_validate_chain_output` ([`workflow.py:180-190`](src/backend/workflow.py#L180-L190)) passes it to
  `model_validate`, which hands the same object back unchecked (confirmed). It only does work in
  tests, where the stand-in model passes raw dicts.
  > **Reviewer comment — Partly agree.** It is redundant for the current production chain but useful
  > for raw fake or alternate injected outputs. Decide after defining typed chain contracts.
- **Late imports add code.**
  > **Reviewer comment — Partly agree.** The LangChain parameter plumbing can be simplified, but the
  > search adapter boundary should remain.
  - LangChain is imported inside `__init__` ([`model.py:91-92`](src/backend/model.py#L91-L92)), so
    the `ChatPromptTemplate` class has to be passed into `_make_chain` as a parameter.
    > **Reviewer comment — Agree.** LangChain is a required dependency; a normal module import makes
    > this code clearer.
  - `DDGSSearchClient` ([`search.py:41-50`](src/backend/search.py#L41-L50)) exists only to import
    `ddgs` late, and the `SearchClient` Protocol exists only to describe that wrapper.
    > **Reviewer comment — Disagree.** The adapter and Protocol form a useful injection boundary for
    > deterministic search tests. Lazy importing may be removed without deleting the boundary.
  - Both libraries are required dependencies anyway, so they can be imported at the top.
    > **Reviewer comment — Partly agree.** Import both normally if startup side effects remain safe,
    > but retain the DDGS adapter and its contract.
- **Options and fields nobody uses:**
  > **Reviewer comment — Partly agree.** The factual inventory is mostly correct, but planned MLflow
  > hooks and useful injection seams should be wired in rather than deleted indiscriminately.
  - No caller passes `temperature`, `seed`, `adaptive_prompt`, `search_prompt`,
    `synthesis_prompt` or `structured_output_method` to `OllamaChatModel`.
    > **Reviewer comment — Agree as an inventory fact; partly agree on removal.** Temperature and
    > seed document deterministic behavior, while prompt/schema injection may support tests and
    > evaluation. Narrow the constructor only after those uses are decided.
  - `prompt_hashes` (and the SHA-256 behind it), `ModelOutputError.parse_failure`, `.detail` and
    `MIN_ADAPTIVE_QUESTIONS` are never read.
    > **Reviewer comment — Partly agree.** Use `prompt_hashes` and useful failure detail in MLflow;
    > remove `parse_failure` and `MIN_ADAPTIVE_QUESTIONS` if no implemented contract needs them.
  - `run_id` is `None` in every response.
    > **Reviewer comment — Agree.** Populate it from MLflow tracking or remove it from the public
    > response until tracking exists; a permanent placeholder adds no value.
  - `emergency_rule` is a result field that [`app.py:31`](src/backend/app.py#L31) strips before
    sending; only one test reads it.
    > **Reviewer comment — Partly agree.** It is useful internal observability, but it need not live
    > on the public result schema if a trace/event record can carry it instead.
- **The same value lives in several places:**
  > **Reviewer comment — Agree with reducing drift, subject to keeping validation at boundaries.**
  - The Ollama URL and timeouts are set twice in `settings.py` (the field defaults and
    `from_environment()`), again in `model.py`, and the search defaults again in
    `from_defaults()`.
    > **Reviewer comment — Agree.** Runtime defaults should have one owner and be passed explicitly.
  - The 4,000-character excerpt limit has two names (`MAX_EXCERPT_CHARS`,
    `MAX_EVIDENCE_CHARS`), and the text is cut twice.
    > **Reviewer comment — Partly agree.** Share one limit constant, but retaining both transport
    > truncation and schema enforcement is valid defense in depth.
  - The recap labels ([`workflow.py:48`](src/backend/workflow.py#L48)) must be kept in the same
    order as the questions in `questions.py` by hand. A `label` field on `StandardQuestion` would
    remove that.
    > **Reviewer comment — Agree.** Store the ID, label, and question text together.
  - `num_predict=900` is a bare number.
    > **Reviewer comment — Agree.** Give it a named setting and account for it in the context budget.
- **Names that mislead:**
  > **Reviewer comment — Agree.** These are small, low-risk clarity improvements after functional
  > work is complete.
  - `ModelOutputError` is also raised for search outages, unsafe queries and "no evidence".
    > **Reviewer comment — Agree.** Rename it to a stage/turn-processing error.
  - `OllamaChatModel` isn't a chat model (LangChain's `ChatOllama` is). It holds the three chains,
    and the workflow calls it `chains`.
    > **Reviewer comment — Agree.** A name such as `OllamaChains` or `OllamaPipelines` matches its
    > responsibility.
  - In `_validate_history`, `expected` holds a role and then a question text
    ([`workflow.py:120`](src/backend/workflow.py#L120),
    [`workflow.py:129`](src/backend/workflow.py#L129)).
    > **Reviewer comment — Agree.** Use `expected_role` and `expected_question`.
- **An unstated contract.** `run_turn(turn, chains: Any, searcher: Any)` doesn't say which methods
  it calls. Task 02 chose `Any` plus a docstring over a Protocol, because nothing type-checks this
  repository. The multi-chain rewrite dropped that docstring, so the three chain methods and
  `search()` should be listed in it again.
  > **Reviewer comment — Agree with the problem.** Prefer small `ChainRunner` and `EvidenceSearcher`
  > Protocols; restoring the docstring is the minimum fallback.
- **Test setup.** [`tests/conftest.py:11`](tests/conftest.py#L11) imports PySide6, so the backend
  tests can't run without the desktop extra installed.
  > **Reviewer comment — Agree.** Move Qt fixtures into a desktop-specific conftest or skip only the
  > desktop test modules when the optional extra is absent.

## Suggested order

1. Push what you have.
   > **Reviewer comment — Agree.** Push the existing committed work immediately; the public repo is
   > still the first commit.
2. Fix the desktop client, and give the README one run section.
   > **Reviewer comment — Agree with the work, now partly completed.** The desktop fix exists locally
   > and needs linting, commit, and push. README consolidation remains open; include the browser
   > failed-first-request fix in this step.
3. Add MLflow, and move the live test's hand-built recording onto it.
   > **Reviewer comment — Agree; now in progress.** The new local implementation covers basic runs
   > and LangChain traces. Complete its documented gaps and push it.
4. Set `num_ctx=8192`, strip page menus, and handle the long-title case.
   > **Reviewer comment — Agree.** Add a total token budget and deterministic parser fixtures too.
5. Fix the matcher word boundaries and add those sentences as tests.
   > **Reviewer comment — Agree, but move this earlier.** It is a current user-visible safety defect.
6. Remove the extra layers and unused options.
   > **Reviewer comment — Partly agree.** Defer broad deletion. First define Protocols and MLflow
   > observability, then remove only layers proven redundant.
7. Keep one error table and cut the README down.
   > **Reviewer comment — Agree.** Make one canonical error contract and link to it elsewhere.

## Progress since the review

- Search failures (problem 3): fixed in commits `65bb2d3` and `8db564b` by a parallel session.
  > **Reviewer comment — Agree and verified.** Keep the long-title problem open separately.
- Desktop client: updated to the current API (task 04 on the local task board), committed as
  `c635c5e`; not pushed.
  > **Reviewer comment — Agree.** The current offline suite covers the new contract, and the latest
  > working tree now passes Ruff.
  - The form now asks only for species and concern.
    > **Reviewer comment — Agree and verified.**
  - Replies show as bubbles, and the assessment as labelled sections with clickable sources.
    > **Reviewer comment — Agree and verified from the implementation and tests.**
  - 422 and 503 replies show their real message instead of "Could not reach the assistant
    service". Qt flags both as network errors, which hid them.
    > **Reviewer comment — Agree.** The updated client correctly prioritizes an HTTP status over
    > Qt's generic network-error flag.
  - A new test sends the desktop's own requests to the real backend code, so the two can't drift
    apart unnoticed again.
    > **Reviewer comment — Agree.** This is the right regression boundary.
- MLflow: first slice done (task 05 on the local task board), committed as `61ce637`; not pushed.
  The run-safety fixes in "Found while fixing", item 8, came after that commit. All MLflow code is
  in `src/mlflow_tracking/`, not `src/mlflow/`: tests put `src/` first on the import path, so a
  folder named `mlflow` would hide the real library.
  > **Reviewer comment — Agree.** The package name avoids shadowing the third-party dependency.
  - Each chat turn is one MLflow run. It records the model, the prompt-file hashes, the species,
    how many questions had been answered, the time taken, the reply kind, and on failure the
    failed stage and reason.
  - Each run holds one trace with every LangChain call's prompt, reply and timing. The `run_id` in
    successful responses is now real, and `prompt_hashes` is used.
  - Checked with the real model and live search, and in the MLflow UI. The tests and the browser
    test server write to a throwaway database, never the project's `mlflow.db`.
  - Still to do, all listed in the execution plan's step 3: a span for search and page fetching,
    per-stage metrics, a run id in error bodies, an analysis script, and moving the live test's
    recorder onto MLflow.
  - Seen with the real model: at the three-question limit, llama3 asked a fourth question and the
    turn failed with a 503 (problem 5). MLflow recorded the failed stage.

## Found while fixing (2026-09-23)

These came up while fixing the desktop client and adding MLflow, after the review above was
written.

### 1. The model tried to ask a fourth question

- **What happened.** In a real chat with llama3 and live search, the owner answered three
  model-generated follow-up questions.
  - The backend then called the model once more, in `ready_or_escalate` mode, and the model returned
    a fourth question.
  - The backend rejected it with a 503. Because the model runs at temperature 0 with a fixed seed,
    Try again would send the same prompt and get the same reply.
  - MLflow recorded the run as FAILED with `failed_stage=adaptive_question`.
- **Why.** The limit of three is enforced by asking the model to stop, then refusing its answer if
  it doesn't. The model is still offered a choice it must never make
  ([`workflow.py:71-94`](src/backend/workflow.py#L71-L94)).
- **Owner decision.** The limit is a plain loop in code. The model is never asked for a question it
  isn't allowed to ask. The owner's sketch, tidied:

  ```python
  answers = []
  for _ in range(MAX_ADAPTIVE_QUESTIONS):  # three at most: the code counts, not the model
      question = model_next_question(turn, answers)  # a question, or None when it has enough
      if question is None:
          break
      answers.append(ask_owner(question))
  # then search and synthesis; no model call can produce a fourth question
  ```

  Counting from 0, a `while count <= 3` loop would allow four questions, so the loop above runs
  exactly three times.
- **Notes for implementing it:**
  - The backend keeps no session between requests, so the loop runs across HTTP turns. The count
    comes from the history the client sends. Once it reaches three, the workflow goes straight to
    search without asking the model for a question.
  - Today that last model call also lets the model raise an emergency after the third answer.
    Under the loop, that check either becomes its own call whose reply cannot contain a question,
    or it is dropped. The phrase matcher still checks every answer either way. This is for the
    owner to decide.
  - The loop as sketched lets the model skip follow-up questions entirely, by returning None on the
    first pass. Today at least one follow-up question is required, which is the other 503 dead end
    in problem 5. Whether that minimum stays is also the owner's call.

### 2. The desktop client hid every 422 and 503

Qt marks any 4xx or 5xx reply as a network error. The old desktop code checked that flag first, so
the owner saw "Could not reach the assistant service" instead of a field correction or the service
message. The independent plan review found this. It is fixed: the client now checks the HTTP status
first.

### 3. Cutting owner text short can hide an emergency

The first version of the desktop fix limited the concern box to 1,000 characters with Qt's
`setMaxLength`. That silently cut a pasted concern. A concern ending "She is now struggling to
breathe" arrived as "...She is now str", and the emergency check never saw the phrase. The
independent diff review found this. It is fixed: an over-long concern is refused with a message.
The rule for any client is to refuse over-long text, never to cut it.

### 4. MLflow linked traces to the wrong run when two turns overlapped

By default, MLflow attaches a new trace to the latest open run in any thread. With two chats
running at once, both traces landed on one run. It is fixed: each turn's trace is started with its
own run's id. A test holds two turns open at the same moment to prove it.

### 5. MLflow wrote some traces to files instead of its database

With MLflow's default background saving, 4 of the 5 traces in the first real chat were written as
files under `./mlruns` instead of into `mlflow.db`. It is fixed: each trace is saved before its turn
returns, and a second real chat wrote nothing outside the database.

### 6. The backend builds the real app when it is imported

`backend/app.py:67` builds the runtime app as soon as the module is imported, so importing it
starts MLflow tracking, including during test collection. The tests work around this by pointing
MLflow at a throwaway database before anything imports the backend. Building the app only when the
server starts (`uvicorn --factory`) would remove the workaround.

### 7. Docker is an example, not a deployment

`Dockerfile`, `compose.yaml` and `.dockerignore` were added by an earlier session (commit
`6719a47`, 2026-09-22). MLflow does not need them.

**Owner decision (2026-09-23).** We are not doing a Docker deployment. The files stay as an example
of how we would do it, and the README says so. They are not tested as part of this project.

### 8. Recording a turn in MLflow could cost the owner their reply

An independent review of the first MLflow commit found three ways the per-turn run broke the chat.
Each was reproduced.

- **Deleting the experiment in the MLflow UI broke every turn.** MLflow's Delete button only moves
  an experiment to a bin. MLflow then refuses to add runs to it, and refuses to select it at
  startup. The first version failed loudly, so every turn, including emergency notices, returned a
  500, and the server would not start.
- **Many turns at once exhausted MLflow's database connections.** With 48 turns arriving together,
  requests failed after a 30-second wait.
- **Rejected requests showed as unexplained failures.** A 422 or an unexpected 500 was recorded as
  a FAILED run with no reason.

The standard answer is that tracking must never change what the app does. OpenTelemetry's
error-handling rules say instrumentation must not throw into the application, and MLflow's own
tracing drops a failed trace and logs it. The owner chose to keep the brief's per-turn run, with
its parameters and metrics, and make it safe with a small change:

- restore a deleted experiment when the server starts;
- answer a turn without a run, with the error logged, when MLflow cannot open one;
- open a new database connection each time (`NullPool`);
- tag every failed turn with its reason.

A failure after the run has opened, such as the experiment deleted mid-turn, still gives the 500.
Covering that few-second window would need a larger rewrite.

## Reviewer execution plan — fully agreed work only

Execute in this order. Each step should finish with focused tests, the full offline suite, and a
clean Ruff run before its commit is pushed.

### 1. Protect the deliverable and finish the client contract work

1. Push the 20 commits already on local `main` so the public repository is no longer the initial
   commit only.
2. Finish and commit the local desktop/API contract work, including
   `tests/test_desktop_backend_contract.py`.
3. Add a browser regression test for a failed initial request, then change retry state so **Try
   again** resubmits intake until the first question has actually been accepted.
4. Push the desktop and browser fixes after the currently clean Ruff and offline test gates pass.

**Exit criteria:** remote `main` contains the implementation; a real backend contract test covers
desktop question, assessment, emergency, 422, and 503 replies; Playwright covers initial-request
retry; offline tests and Ruff pass.

### 2. Fix the deterministic emergency matcher

1. Add all seven sentences from problem 1 as failing regression tests.
2. Add the missing word boundaries around the ingestion verb and urination-term groups.
3. Normalize a trailing straight or typographic possessive before the pet-subject lookup.
4. Add `isn't` and `wasn't` breathing variants.
5. Keep the existing pet-subject requirement for collapse until the deferred policy review below.

**Exit criteria:** the three ordinary sentences do not escalate; the three possessive/contraction
emergencies do; existing denial and near-miss tests still pass.

### 3. Complete the uncommitted MLflow implementation

1. Review and retain the new MLflow dependency and `src/mlflow_tracking/` package.
2. Keep one run per chat turn and complete child spans or equivalent stage records for deterministic
   routing, adaptive decision, query generation, search/fetch, and synthesis.
3. Complete recording of prompt name/hash, model, structured response, stage duration,
   success/failure reason,
   evidence/source metadata, and the application run ID. Do not record raw owner identifiers or
   secrets.
4. Add the run ID to handled error responses without exposing provider diagnostics.
5. Replace the live-journey harness's parallel JSON timing implementation with the same tracking
   abstraction; retain exportable local artifacts only where they add review evidence.
6. Add the promised search/fetch spans and a small analysis/reporting entrypoint over recorded runs.

**Exit criteria:** a deterministic test proves every required stage is tracked; a failed stage has
its class and stable reason; `prompt_hashes` and `run_id` are no longer placeholders; MLflow storage
is ignored by Git.

### 4. Prevent model-choice dead ends

1. Define separate structured response schemas for `question_required`, `question_or_ready`, and
   `ready_or_escalate`.
2. Bind the correct schema before each adaptive model invocation.
3. Retain boundary validation for malformed provider output.
4. Update tests so the first schema cannot express readiness and the cap schema cannot express a
   fourth question.

**Exit criteria:** the two deterministic 503 retry dead ends are unrepresentable in generated
schemas, while urgent escalation remains available in every mode.

> **Owner decision (2026-09-23).** For the limit of three, use a code-enforced loop instead of a
> cap schema. After the third answer the workflow goes to search without asking the model for a
> question, so a fourth question cannot happen. See "Found while fixing", item 1.

### 5. Bound synthesis context and improve evidence extraction

1. Pass `num_ctx=8192` explicitly and promote `num_predict` to a named setting.
2. Add a token-budget function covering system text, owner history, structured-output/schema
   overhead, all evidence, and reserved output tokens.
3. Prefer `<main>` content when present; otherwise extract visible body text while ignoring
   `header`, `footer`, `aside`, `nav`, scripts, styles, forms, and SVG.
4. Add local HTML fixtures for the main-content and fallback paths.
5. Normalize or reject an over-300-character title per result without discarding other evidence.
6. Cap total page-fetch attempts per turn.

**Exit criteria:** four worst-case evidence items cannot evict the synthesis rules; menu-only text
does not consume the excerpt budget; one malformed title cannot fail an otherwise usable turn.

### 6. Make the final-turn time budget coherent

1. Define a server-side total deadline for the final turn and budgets for each model, search, and
   fetch stage.
2. Derive a distinct final-turn client timeout from that deadline, with a small transport margin.
3. Keep the agreed page-fetch-attempt cap from step 5.
4. Document that a timed-out/disconnected synchronous request may still be running and ensure the
   UI does not imply cancellation.

**Exit criteria:** documented and implemented budgets agree; deterministic timeout tests do not
wait on real clocks; the client cannot time out before the server's declared budget under normal
operation.

### 7. Replace string-guessed history errors

1. Give invalid-history failures structured codes for incomplete pair, wrong role, changed standard
   question, and excessive history.
2. Map those codes to owner-facing text only in the HTTP error boundary.
3. Map Pydantic's `history` length failure to the same excessive-history response.
4. Remove exception-text substring inspection and its unreachable branch.

**Exit criteria:** each invalid history class has its own deterministic 422 test and changing an
internal exception sentence cannot change the public response.

### 8. Tighten contracts, configuration, and optional test dependencies

1. Add small Protocols describing the three chain methods and `search()` used by `run_turn`.
2. Give runtime URL and timeout defaults one owner and pass them explicitly into adapters.
3. Put each standard question's recap label beside its ID and text.
4. Move Qt fixtures to desktop-specific test setup so base/backend tests run without PySide6.
5. Apply the agreed clarity renames: stage-processing error, Ollama chains/pipelines,
   `expected_role`, and `expected_question`.
6. Import required LangChain types normally and remove the resulting template-class parameter
   plumbing. Retain the DDGS adapter and search Protocol.

**Exit criteria:** backend-only installation can run backend tests; workflow dependencies are
discoverable without reading fake implementations; runtime defaults cannot silently diverge.

### 9. Consolidate the handoff documentation

1. Put the one-sentence project description and one canonical quickstart at the top of the README.
2. Remove duplicate setup/run command blocks while retaining links to detailed component docs.
3. Keep one canonical failure-contract table and link to it from the backend README.
4. Correct the final-turn timeout and Pydantic history descriptions.
5. Remove the speculative snippet sentence unless snippet evidence is actually implemented.

**Exit criteria:** every documented command is exercised, the README has one run path per client,
and error behavior is defined in one place.

## Later review notes — partly agreed items

Do not include these in the implementation sequence until their policy or design tradeoff has been
decided:

1. **README severity:** decide how much design rationale belongs in the top-level README. It is too
   repetitive, but it already satisfies the brief's setup/run requirement.
2. **Scope causation:** treat the two UIs and retrieval work as evidence of misplaced priority, not
   as proof that they literally caused MLflow to be omitted.
3. **Named-pet collapse matching:** decide whether the safety benefit of matching every occurrence
   of "collapsed" outweighs false alarms for human or object subjects.
4. **Exact client timeout:** approve the server budget first; do not independently hard-code 180
   seconds.
5. **Owner-facing history errors:** do not implement the original suggestion by embedding final UI
   prose in workflow exceptions. The execution plan uses structured codes, but the exact code and
   wording taxonomy should receive a quick API-contract review.
6. **Error-layer cleanup:** after Protocols and MLflow exist, reassess `_call_stage`, the search
   boundary catch, the duplicate no-evidence guard, and `_validate_chain_output`. Do not remove
   defensive boundaries merely because the current production adapter already validates.
7. **Failure classification:** replace `_failure_reason` heuristics, but retain stable internal
   reason codes even though every handled failure intentionally has the same public 503 text.
8. **Constructor options:** decide which prompt/schema injection options support tests or evaluation
   before narrowing `OllamaChatModel`'s constructor.
9. **Planned observability fields:** use `prompt_hashes`, useful exception detail, and `run_id` for
   MLflow; separately decide whether `emergency_rule` belongs on an internal result or only in the
   trace record.
10. **Excerpt enforcement:** share the 4,000-character constant, but decide whether transport
   truncation and schema validation should both remain as defense in depth.
11. **Search imports:** normal top-level import is reasonable, but do not remove the DDGS adapter or
    `SearchClient` Protocol solely to save lines.
12. **Broad dead-code removal:** remove `parse_failure` and `MIN_ADAPTIVE_QUESTIONS` if MLflow work
    confirms they have no contract, but avoid a wholesale cleanup until functional milestones are
    complete.
