# VetAI technical test: final implementation plan

## 1. Flow and delivery

**What the person using it gets:** A small PySide6 desktop chat. They enter their pet's species and concern, plus duration, whether it happened before, and whether symptoms are constant or intermittent (`unknown` is allowed). They may receive zero, one, or two relevant follow-up questions. The final response recaps *only what they reported*, offers one or two grounded points to discuss with a veterinarian, and states that it is not a diagnosis. If a limited emergency phrase rule matches, they instead receive a fixed notice to contact an emergency veterinarian; no model-generated reassurance is shown.

```text
Desktop intake -> POST /v1/chat -> validate -> emergency phrase check
                                         | match: fixed emergency notice
                                         | otherwise: LangChain + Ollama
                                         v
                         one follow-up question OR final recap
                         (maximum two follow-ups in this chat)
```

The desktop shows a pending state during each request, displays the reply or a clear connection error, and offers "New concern" after a final recap or emergency notice. The backend attempts to record each valid turn and its timing in local MLflow; logging failure does not hide a reply. There is **no diagnosis, treatment advice, general urgency band, or medical claim** in the result. The fixed emergency route is a narrow escalation heuristic, not validated clinical triage.

**What we deliver:** a runnable Python desktop client and FastAPI backend, one LangChain/Ollama chain, a small deterministic safeguard, local MLflow transcripts and analysis, automated tests and CI, locked dependencies, and a root README that lets a reviewer run and inspect the demo. The [three-page brief](../e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf) calls this a pet-triage task and prioritises internals over UI polish. This implementation deliberately uses the narrower term **pet concern question flow**; `workflow.py` names the code honestly. The submission is a public GitHub repository, not a hosted service.

## 2. Behavioural decisions

1. **Deterministic intake:** species, concern, duration, previous occurrence, and constant/intermittent pattern are captured by the form. Unknown values are acceptable; the model need not repeat known questions.
2. **Deterministic safety gate:** check owner-authored free text (concern, duration, and every owner answer) before each model call; never scan assistant-authored questions as owner symptoms. A match returns the fixed emergency notice. Rescanning all owner text makes a previously reported warning sign persist in later turns. Match only curated phrases: explicit negation may suppress a match, while uncertain possible medication/toxin ingestion still receives the notice ([test cases](test-cases.md)). This is a demo policy, not general language understanding.
3. **Adaptive questions:** on a non-emergency turn, one LangChain/Ollama call proposes either a single useful follow-up or the final recap. The model may stop immediately or after one question. Exactly one prior question still permits a second question or a recap in ordinary mode. After two follow-ups, the backend requests `summary_only` and accepts no further question. This is a useful hybrid of predictable control flow and genuinely adaptive wording.
4. **Bounded, structured result:** use a Pydantic result with `kind` (`question` or `summary`) and bounded `reply`, via [ChatOllama's `with_structured_output`](https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama/with_structured_output). Validate the result again in the workflow and append a fixed non-diagnostic suffix to successful summaries ([example](test-cases.md)). On parse failure, prohibited third question, timeout, or empty response, return a non-diagnostic service error and log the failure; do not add an automatic retry in the first version. Each normal turn therefore makes at most one model call.
5. **Honest memory limit:** the desktop keeps the complete *current* short chat in memory and sends it with each request. During an active chat, history is zero to two alternating `{role: assistant}` questions and `{role: user}` answers, ending in a user answer; final summaries and emergency notices end the chat and are never sent back as history. The backend validates that sequence and counts assistant messages as prior questions. Thus the two-question cap permits at most four history messages; malformed or longer history is rejected, not truncated. A custom client can still omit or alter past messages, so this is not tamper-proof or resumable session state.

The final recap should avoid invented symptoms, specific tests such as bloodwork, treatment instructions, and unsupported certainty. Its "points to discuss" are phrased as questions grounded in the user's facts, not recommendations for clinical procedures.

## 3. Scope and trade-offs

| Decision | Choice for this test | Why / cost |
| --- | --- | --- |
| UI and API | PySide6 desktop UI calling one FastAPI endpoint over HTTP | Two local processes add setup, but clearly separate presentation and behaviour. Keep the window plain. Svelte would add a TypeScript/toolchain learning cost without improving this brief. |
| Model | Ollama only; the workflow calls one method, `propose(turn, mode)`, on whatever it is handed | Enables a later OpenAI adapter and fake-model tests, without a plugin framework, an interface class, or a second provider today. |
| Chat history | Complete current chat in desktop memory, sent on each request | Enough context for two follow-ups; no server session, long-term memory, or database. |
| Emergency check | Small deterministic rules before the model | Predictable escalation for selected phrases, with explicit false-positive and false-negative limits. |
| Tracking | Local, file-backed MLflow | Meets the brief without a tracking server. Transcripts are for analysis, not future prompt memory. |
| Configuration | Short YAML defaults loaded into typed Python settings | Makes model, prompt path, and local URLs visible; no generic rule engine or provider registry. |
| Dependencies | `pyproject.toml` plus committed `uv.lock`, Python 3.11 | A reviewer can use `uv sync --locked`; CI runs the same locked environment. |
| Deferred | Postgres, customer history, RAG, context-provider interface, ERD, agents, deployment, urgency grades | Each introduces a new data or safety problem without satisfying an additional current requirement. |

The exact Ollama model is chosen during implementation after a local structured-output smoke test. Record its tag and observed digest; do not pretend a model tag alone is immutable.

## 4. Architecture and source layout

```text
PySide6 desktop -> HTTP request -> FastAPI /v1/chat -> workflow
                                                   /    |      \
                                         safeguards   model     MLflow
                                                       |
                                                 LangChain/Ollama
```

The desktop knows the API contract and its own display state; it imports no backend, LangChain, Ollama, or MLflow code. The backend owns validation, safety routing, prompting, model calls, and tracking. The desktop uses Qt's asynchronous [`QNetworkAccessManager`](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QNetworkAccessManager.html) to keep the window responsive. This is a thin wrapper, not a second application layer.

```text
README.md                    # Project setup, run instructions, and scope
pyproject.toml, uv.lock      # Declared and locked dependencies
.github/workflows/ci.yml    # Headless lint and test checks
src/
  README.md                  # Frontend/backend ownership
  frontend/
    README.md                # Desktop design and HTTP boundary
    app.py                   # Intake, chat, and in-memory history
    api_client.py            # Async HTTP, timeout, and error mapping
  backend/
    README.md                # Request flow and backend ownership
    app.py                   # Route and small request/response models
    schemas.py               # Shared data shapes, fixed wording, limits, validation
    workflow.py              # Safety -> model -> checked response
    model.py                 # Prompt file and Ollama adapter
    safeguards.py            # Emergency rules and fixed notice
    tracking.py              # MLflow runs and simple analysis command
    settings.py              # Load and validate configuration
config/
  README.md                  # Config precedence and secret policy
  defaults.yaml              # Safe defaults only
prompts/
  README.md                  # Prompt purpose and versioning
  question_flow.md           # Versioned prompt text
tests/
  README.md                  # Test layers and fake-model strategy
  test_chat.py               # API/workflow with fake model
  test_safeguards.py         # Positive, ordinary, and negated phrases
  test_tracking.py           # MLflow run content and analysis
  test_api_client.py         # Desktop HTTP/error mapping with fake replies
  evaluate.py                # Opt-in local Ollama run on fixed synthetic cases
  cases.json                 # Small, versioned evaluation set
documentation/
  README.md                  # Design document index
  implementation-plan.md
  test-cases.md              # Synthetic examples and acceptable responses
```

**Added during implementation: `schemas.py`.** The original layout kept the small models beside
the code that uses them. One file was split out anyway, because `workflow.py` must be testable
without LangChain installed or imported. Shared types in `model.py` would have been sound layering
— the dependency runs one way — but it would have put the LangChain import chain into every
workflow test run. `schemas.py` holds data shapes, limits, and the two error types, and imports
nothing from the project. It decides nothing: the rules that use those shapes, and the fixed
emergency notice and summary suffix, live in `workflow.py`, which is the only module that produces
user-facing text of its own. Layering is `schemas.py` <- `model.py` <- `workflow.py` <- `app.py`,
with `safeguards.py` importing nothing from the project at all.

`workflow.py` should stay readable end to end. The small API models can live beside the sole route, and the interface beside its only adapter. Split files only when actual code, not hypothetical future code, warrants it. A separate `safeguards/` package and empty retrieval seam would add navigation without current behaviour.

Each main folder has a short `README.md` explaining ownership and one key decision, as requested. They are not eight copies of the root README; update only when their actual folder changes.

### API contract

`POST /v1/chat` takes an `intake` object plus the complete current-chat `{role, content}` sequence defined above. Intake has `species` (`dog` or `cat`), `concern` (1–1000 characters after trimming; whitespace-only is invalid), `duration` (brief text up to 100 characters or unknown), `previous_occurrence` (`yes`, `no`, or `unknown`), and `pattern` (`constant`, `intermittent`, or `unknown`). Each history message is at most 1000 characters; the model's pre-disclaimer `reply` is at most 1200. On success it returns `{reply, kind, run_id}`, where `kind` is `question`, `summary`, or `emergency_notice`, and `run_id` is a string or `null` if tracking failed. These kinds are UI states, not graded clinical classes. Invalid input/history gets HTTP 422. Model failure gets HTTP 503 with `{error, run_id}`; the error is safe and non-diagnostic, and `run_id` is `null` only if no failure run was recorded. The desktop retains the owner's answer for manual retry, but the backend does not retry automatically. `GET /health` is a small local startup check. FastAPI serves these HTTP endpoints; it is not an alternative to HTTP.

The exact JSON schema lives beside the route and is exercised by API tests. There is no user ID, account, persisted chat ID, clinical assessment record, agent-run record, or retrieval API.

## 5. Data and the ERD decision

**No ERD in this release.** There is no application database or entity relationship to draw. The desktop holds the current chat in memory; the backend processes one request at a time; MLflow stores run artifacts for analysis. These are distinct lifetimes, not three databases.

The three data lifetimes are:

| Data | Where it lives | Used for |
| --- | --- | --- |
| Intake and complete current-chat messages | PySide6 process memory, sent in each request | Immediate follow-up context |
| Current request/response | Backend memory during one request | Prompting and response construction |
| Transcript and run metrics | Local `mlruns/`, ignored by Git | Inspection and MLflow analysis |

MLflow transcripts are **not** application memory. If a later requirement needs saved customers or pet histories, define access and retention rules first, then model actual persisted entities in an ERD.

### Future work: customer records and retrieval

Postgres becomes useful for identifiable records across sessions. RAG becomes useful when answers must cite a curated, versioned document set. Neither is needed to demonstrate this question flow; no empty `ContextProvider` or vector index is added now. A later RAG design would also need retrieval-specific evaluation, but MRR/MMR have no role in the current test.

## 6. Safeguards and evaluation

`safeguards.py` checks a small set of source-backed warning phrases before invoking Ollama. A match returns a fixed emergency notice; the model cannot turn it into a routine question. This is **limited illustrative escalation logic**. Keyword rules can miss emergencies and misread negation or quoted text, so this demo must not be represented as safe for veterinary use.

Start with a handful of examples drawn from [Cornell's emergency guidance](https://www.vet.cornell.edu/hospitals/services/emergency-and-critical-care-0), such as difficulty breathing, collapse, suspected toxin ingestion, and inability to urinate. Put the source beside the rules. Test clear positives, one near miss per rule, and a few case/punctuation variants; do not build a general negation parser. [ASPCA guidance](https://www.aspca.org/pet-care/general-pet-care/emergency-care-your-pet) supports contacting a veterinarian or poison control for suspected ingestion, but this demo keeps one region-neutral fixed notice rather than a US-specific hotline. A clinician would need to review the policy before real-world use.

The required evaluation is a [small fixed synthetic case set](test-cases.md) plus deterministic tests. Cover complete/unknown intake, zero/one/two follow-up paths, safety-rule matches and negations, malformed structured output, model timeout, final recap, and non-diagnostic service errors. Use a fake model for normal CI. Run the fixed set against local Ollama in a separate opt-in evaluation command; CI must not download a model or require a GUI display.

For the fixed case set, log an **offline evaluation run** to MLflow with prompt/model versions and aggregate counts: safety-rule hits, response kinds, structured-output failures, follow-up count distribution (0/1/2), and latency. Review about five model-produced cases by hand for relevance, factual grounding, and non-diagnostic wording. A reference-free LLM judge *can* assess such qualities without gold answers ([MLflow docs](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/)), but it is an optional, time-boxed comparison against those human notes, never a runtime gate or claim of clinical validation. Do not build a judge pipeline for the take-home.

## 7. MLflow, reproducibility, and privacy

For each valid turn, attempt **exactly one** local MLflow run with response kind or failure reason, success/failure, elapsed time, `parse_failure` (including schema validation), model tag/digest, prompt SHA-256, and Git SHA when available. Store the bounded transcript as a local artifact. Failed Ollama calls should still yield a failure run. Tracking is best-effort at runtime: if MLflow cannot write, log a visible backend warning and return the already determined question, recap, or emergency notice with `run_id: null`; never suppress an emergency notice because tracking failed. A simple analysis command prints run count, response-kind and failure counts, follow-up distribution from evaluation runs, and nearest-rank p50/p95 latency **with sample size**; a tiny sample is descriptive, not statistically persuasive.

Pin dependency versions in `uv.lock`, use `temperature: 0` and a fixed seed where supported, record the prompt hash and actual Ollama model digest, and run the same synthetic cases after a prompt or model change. These improve repeatability, but local model inference is not guaranteed bit-for-bit deterministic. Explicit logging is the baseline; [`mlflow.langchain.autolog()`](https://mlflow.org/docs/latest/genai/flavors/langchain/autologging) is an optional short experiment only if it adds useful traces without duplicate runs or unwanted transcript exposure.

Keep `mlruns/` and real user text out of Git. The root README must say that local transcripts can contain sensitive owner-entered information and explain how to delete the local run directory. Use synthetic examples for tests and screenshots. There is no claim of automatic de-identification or configured retention policy in this take-home.

## 8. Configuration and local operation

`config/defaults.yaml` should contain only a few safe fields, for example:

```yaml
model:
  provider: ollama
  name: <chosen-model-tag>
  base_url: http://localhost:11434
  temperature: 0
  seed: 42
prompt_file: prompts/question_flow.md
max_follow_up_questions: 2
mlflow_tracking_uri: ./mlruns
```

`settings.py` validates these backend values; `OLLAMA_BASE_URL` may override the local URL. The frontend reads `BACKEND_API_URL` separately. Configuration selects an existing prompt file but does not dynamically load arbitrary classes. Set a short model timeout; the exact chosen model, observed digest, and run commands belong in the root README once verified on the available machine.

The root README should provide commands to install with `uv sync --locked`, start Ollama, pull the chosen model, start FastAPI, launch PySide6, run tests, and inspect MLflow. A backend-only container recipe is optional future polish; the desktop stays native, and deployment is not required.

## 9. Build order and acceptance checks

1. Add package metadata/lockfile, safe config, prompt, `.gitignore`, and headless CI (`ruff` plus `pytest`). Keep folder READMEs accurate as code arrives.
2. Write API models, fake-model workflow tests, small emergency rules, and structured-output validation. Keep each rule traceable to one test and source.
3. Connect LangChain/Ollama and MLflow. Verify a normal, malformed-output, and emergency case locally; record the chosen model digest.
4. Add the thin PySide6 client and simple request/error-mapping tests, the opt-in fixed-case Ollama evaluation, and the MLflow report. Run the setup from a clean environment and manually smoke-check the desktop.

The work is done when:

- A user can provide structured intake, receive zero to two relevant follow-up questions, and see a factual recap plus grounded points to discuss with a vet; the UI calls only the FastAPI HTTP endpoint.
- The desktop stays responsive while the request runs, displays connection/time-out errors, and starts a new flow after a recap or emergency notice.
- One LangChain chain invokes the configured Ollama model and returns a validated Pydantic result; the model can be faked in tests.
- A known emergency phrase produces the fixed emergency notice without a model call.
- When local tracking works, exactly one run per valid turn contains a bounded transcript, response kind or failure reason, model/prompt/Git versions, parsing status, and latency; an offline fixed-case run and short report compare changes. A tracking write failure emits a backend warning without hiding the response.
- Invalid requests and Ollama failures produce understandable, non-diagnostic errors; model failures are tracked when MLflow is available.
- Headless CI passes `pytest` and `ruff` from the locked environment; the README allows another person to run the demo without guessing setup steps.
- No secrets, `.env`, `mlruns/`, or real user transcripts are committed to the public repository.

## 10. Decisions to explain in the interview

- Why the frontend calls an API despite the small scope: it makes the boundary between presentation and application behaviour visible.
- Why the workflow is explicit: one model call per normal turn and the fixed emergency path can be read and tested end to end.
- Why the workflow calls one method on an object it never imports: the provider can change while the request flow stays the same, and it takes no interface class to arrange that.
- Why current-chat history, MLflow transcripts, and long-term memory have different purposes; the first two do not create a trusted, persistent session.
- Why information goals are fixed while the model chooses the next question, and why the backend controls when the flow ends.
- Why structured intake plus at most two adaptive questions is easier to test and explain than either a fully scripted or unbounded chat.
- Why there is no database, ERD, RAG index, or agent framework, and why an LLM judge is optional offline analysis rather than runtime authority.
- What the emergency rules cover, where they can fail, and why tests and source links do not make them clinically validated.
- How the fixed evaluation cases, locked environment, prompt hash, model digest, and MLflow runs make a small demo inspectable without overclaiming determinism.
