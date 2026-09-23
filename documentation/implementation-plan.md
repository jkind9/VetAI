# VetAI implementation plan

## 1. Product outcome

VetAI is a local demonstration of a bounded, multi-chain pet-concern conversation. It does not
diagnose, prescribe, rank conditions, or decide that a pet is safe. Its purpose is to collect a
clearer history, retrieve relevant information from a reviewed source list, and help an owner
prepare for a conversation with a veterinarian.

The owner gets:

1. a chat rather than a long intake form;
2. three short, predictable questions;
3. between one and three adaptive LLM questions;
4. a source-grounded `possible_problem` or `nothing_flagged` result split into reported facts,
   possible areas, suggested actions, questions for a veterinarian, and sources; or
5. a fixed emergency notice when either the narrow phrase matcher or the adaptive model escalates.

The original brief prioritises LangChain usage and engineering internals over interface polish.
This design therefore makes the distinct LangChain stages and their boundaries visible and
testable. Each turn is recorded in MLflow (`src/mlflow_tracking`): one run per turn, with the
turn's chain calls traced inside it.

## 2. Ordered conversation

```text
species + concern
      |
      v
validate request and history
      |
      v
scan all owner-authored text for curated emergency phrases
      | match
      +--------------------------> fixed emergency notice; end
      |
      v
three deterministic standard questions
      |
      v
adaptive-question chain: question / ready / urgent escalation
      | urgent
      +--------------------------> fixed emergency notice; end
      |
      v
minimum 1, maximum 3 answered adaptive questions
      |
      v
ready decision, including final ready-or-escalate check at the cap
      |
      v
search-query chain (neutral, short queries derived from all answers)
      |
      v
approved-source web search and bounded page extraction
      |
      v
post-search evidence-synthesis chain
      |
      v
structured assessment; end
```

The standard questions are, in order:

1. **Duration:** “How long has this been happening?”
2. **Previous occurrence:** “Has this happened before?”
3. **Pattern:** “Is it happening constantly, or does it come and go?”

The first adaptive question is mandatory unless the model escalates. After the owner answers it,
the adaptive chain may ask another useful question, declare the history ready for search, or
escalate. A third adaptive question is the hard maximum. The code counts the questions: after the third
answer the workflow goes straight to search without asking the model, so a fourth question cannot
be requested. The phrase matcher still checks that answer first.
Search never runs before the owner has answered at least one adaptive question and never runs before
the three standard questions.

## 3. Three LangChain responsibilities

### Adaptive-question chain

Receives the complete owner history and decides one thing: escalate to the fixed emergency route,
ask exactly one relevant question, or (after the mandatory first adaptive answer) declare the
history ready for search. It is instructed to reason over meaning, misspellings, and awkward wording
rather than exact keywords. It never writes the emergency notice, suggests causes, retrieves
information, or writes the final result.

### Search-query chain

Runs only after questioning is complete. It returns one to three short, neutral queries that
describe the pet, reported concern, timing, pattern, and relevant answers. It must not include
names, addresses, email addresses, telephone numbers, quoted transcript passages, diagnoses, or
instructions to the search engine. The application validates queries before sending them outside
the local machine. The retrieval adapter requests at most three raw results for each generated
query, then independently validates every returned URL and redirect.

### Evidence-synthesis chain

Runs only when approved-source evidence was retrieved. It receives source IDs and bounded excerpts
as untrusted evidence. It may produce broad areas a veterinarian may consider, but cannot diagnose,
rank likelihood, prescribe treatment, invent a URL, or cite an unknown source ID. Every possible
area and every suggested action must cite at least one retrieved source ID.

## 4. Structured result

The final API result is structured rather than one free-form paragraph:

- `outcome`: `possible_problem` or `nothing_flagged`; emergency is returned before synthesis;
- `outcome_wording`: fixed application text for that outcome, never model wording;
- `what_you_reported`: application-constructed, labelled recap copied from the initial concern and
  owner answers; it is not part of the synthesis model's output schema;
- `possible_areas`: broad, non-ranked areas a veterinarian may consider, each with source IDs;
- `suggested_actions`: source-backed, low-risk steps such as observing a change, recording an
  episode for the veterinarian, or simple supportive actions when the evidence supports them;
- `questions_for_veterinarian`: grounded questions the owner may want to raise;
- `sources`: titles, organisations, and HTTPS URLs derived by the workflow from retrieved evidence;
- a fixed non-diagnostic statement owned by the application.

The model never supplies source URLs. It supplies source IDs; the workflow validates those IDs and
constructs the displayed source list from evidence actually retrieved.

Post-result chat is deferred. The completed view offers **New concern**. A bounded “Ask another
question” mode can be added later with its own safety and grounding contract.

## 5. Conversation state

The desktop sends the complete current conversation with every request. The backend stores no
session. A valid active history is zero to six complete assistant-question/owner-answer pairs:

- pairs 1–3 are the exact standard question prefix;
- pairs 4–6 are adaptive questions;
- every assistant message is immediately followed by one non-blank owner answer;
- assessment and emergency results end the conversation and are never sent back as history.

The backend validates alternation, length, and the fixed three-question prefix. A custom client can
still alter adaptive history because there is no trusted server session; that is an explicit demo
trade-off.

## 6. Safety and evidence boundaries

The deterministic emergency matcher runs before every question, model call, search call, and
synthesis call. It scans only the initial concern and owner answers, never assistant questions,
search queries, retrieved pages, or generated output. A match ends the conversation before any
model call. If it does not match, every adaptive decision can still escalate from context; the model
chooses only the route and the application supplies the same fixed notice. Neither route can lower
or override the other.

Search is limited by [`approved-sources.md`](approved-sources.md) and the machine-readable catalog
in `config/approved_sources.toml`. A `site:` clause improves relevance but is not a security
boundary: every returned URL and final redirect target must use HTTPS and match an approved host or
its subdomain. Retrieved text remains untrusted prompt input.

Only short generated queries leave the machine. The raw conversation stays local. This reduces
disclosure but is not a guarantee of anonymisation. Search providers and approved websites can see
the query or requested URL and the machine's public IP.

If no approved evidence is available, the application returns a service failure. It does not ask
the model to produce an unsourced assessment.

## 7. Failure and retry policy

There are no automatic model retries, alternative models, or model-written default medical
responses in this milestone. The search adapter makes one bounded repeat of the exact same plan
only when every provider call failed in its first attempt; it never rephrases the query, replans,
or swaps client. A failed structured response, model call, search, or synthesis returns the stable
service error and preserves the current owner draft for a manual **Try again**. Input and history
errors instead ask the owner to correct the named field. Individual unapproved or unfetchable search
results are discarded, and a provider failure from one query does not discard raw results returned
by another query.

The full error-to-action contract is in [`failure-handling.md`](failure-handling.md) and the backend
operator matrix is duplicated in [`../src/backend/README.md`](../src/backend/README.md).

## 8. Architecture

```text
PySide6 desktop --\
                  -> FastAPI /v1/chat -> workflow state machine
Svelte browser --/                         |       |        |
                                     safeguards  chains   search adapter
                                                     \       /
                                                 grounded result
```

- `frontend/local/app.py`: native owner-visible state, message bubbles, and pending state.
- `frontend/local/api_client.py`: native asynchronous HTTP and public response parsing.
- `frontend/public`: Svelte browser client served by the backend from its built `dist/` directory.
- `backend/workflow.py`: state transitions, safety order, caps, citation validation, final result.
- `backend/questions.py`: immutable standard-question catalog.
- `backend/model.py`: three LangChain/Ollama chains and prompt loading.
- `backend/search.py`: query privacy validation, search, allowlist enforcement, extraction limits.
- `backend/approved_sources.py`: source-catalog loading and host validation.
- `backend/schemas.py`: request, chain-output, evidence, and result shapes.
- `backend/app.py`: dependency composition and HTTP route.
- `mlflow_tracking/chat_runs.py`: one MLflow run per turn, with the turn's LangChain calls traced.

The workflow depends on duck-typed chain and search objects. Tests supply stage-aware fakes, so
ordinary tests need neither Ollama nor network access. The browser E2E suite builds the production
Svelte bundle and drives it against a hosted FastAPI process while retaining those deterministic
model and search boundaries.

## 9. UI contract

The initial form contains species and concern only. **Send concern** immediately shows the owner's
concern in a right-aligned owner bubble and shows a visible assistant pending state. Standard and
adaptive questions appear in left-aligned VetAI bubbles. Answers appear separately in owner
bubbles. The final assessment uses labelled sections inside an assistant result surface.

On a failed request, the current answer remains editable and **Try again** is visible. A successful
question commits the submitted pair. Assessment or emergency ends the flow and exposes **New
concern**. Starting a new concern clears every bubble and all in-memory state.

## 10. Deferred milestones

- an MLflow span for the approved-source search step, and per-stage timings as run metrics (runs
  per turn and traced model calls already exist);
- automated semantic validation and human-review sign-off for the recorded real-model and
  live-search evaluations;
- response-content safeguards beyond citation validation;
- bounded post-result follow-up questions;
- clinical review of source policy and emergency rules;
- persistence, accounts, customer/pet history, RAG/vector storage, deployment, and an ERD.

MLflow is required by the assignment. Tracking of each turn exists; the first item above extends
it.
