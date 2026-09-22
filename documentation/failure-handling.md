# Failure handling for the next chat implementation

This is the implementation contract for the next step: connect the existing backend workflow to
`POST /v1/chat`, then add a small PySide6 chat so a person can send real turns to Ollama and inspect
the result. The [backend README](../src/backend/README.md) describes the code that exists today;
the HTTP route, desktop client, tracking, and model-response content safeguard are still planned.
The [test cases](test-cases.md) provide the behavioural examples referred to below.

## Rules at the boundary

1. Invalid intake or chat history returns HTTP `422`. Show a specific field or history problem so
   the owner can correct it. Do not call the model and do not shorten malformed history.
2. A model call failure, unusable model reply, question-cap violation, or rejection by a future
   response safeguard returns HTTP `503` with **the same** owner-facing text every time:

   > The assistant could not complete this response. Please try again or contact a veterinarian if concerned.

   This is the exact wording from [case C3](test-cases.md#c-contract-and-failure-examples). Define
   it as an application-owned constant at the HTTP boundary. Never ask the model for fallback text,
   never expose the failed model reply, and never put provider exception details in the response.
3. Keep the current intake, displayed question, and owner's answer available after any failure.
   Retry only when the owner presses **Try again**. A failed attempt does not advance chat history
   or consume one of the two follow-up questions.
4. A normal turn makes at most one model call. Disable automatic retries in the desktop HTTP client,
   route, workflow, and model adapter. Check any provider library retry setting when wiring it in.

The fixed emergency notice is a successful `200 emergency_notice`, not a service error. A matched
emergency phrase bypasses the model entirely. A failed MLflow write is also not a chat failure: log
a backend warning and return the determined result with `run_id: null`.

## Failure map

| Failure or outcome | Detected in | HTTP result | Desktop behaviour | Internal record |
| --- | --- | --- | --- | --- |
| Missing field, wrong enum, blank/overlong concern or message | FastAPI request validation using `schemas.py` limits | `422` with an issue naming the field | Keep form and draft; highlight the field for correction | No model call; no chat-turn run |
| Incomplete, out-of-order, or over-four-message history | `workflow._validate_history` raises `InvalidTurnRequest` | `422` with a history issue | Keep intake, displayed chat, and draft; offer correction or **New concern** | No model call; no chat-turn run |
| Ollama timeout, connection failure, or other provider exception | `model.py` / `workflow._ask_model` raises `ModelOutputError` | `503` and fixed service text | Show error and **Try again**; retain draft | Record `timeout`, `connection`, or `model_call_failed` if tracking exists |
| Reply cannot be parsed or fails `ModelReply` validation, including blank/overlong text or an illegal kind | Adapter or `workflow._ask_model` | Same `503` | Same service error; do not display raw reply | `invalid_model_output`; `parse_failure=true` |
| Model asks a third question | `workflow.run_turn` after reply validation | Same `503` | Same service error; do not display third question | `question_limit_violation`; `parse_failure=false` |
| Future response safeguard rejects a well-formed reply for a defined content rule | Response-check block in `workflow.py`, after `ModelReply` validation and before a reply is returned | Same `503` | Same service error; do not display rejected text | A named safeguard-rejection reason; `parse_failure=false` |
| Desktop cannot reach the API or its request times out before receiving HTTP | `frontend/api_client.py` | No HTTP response | Show a clear connection/timeout message and **Try again**; retain draft | Backend may have processed the request; do not assume it did not |
| MLflow write fails after an outcome is determined | Future `tracking.py` call at the API boundary | Keep the determined `200` or `503`; `run_id: null` | Show the determined reply or error normally | Log a backend warning; do not call the model again |
| Unexpected application bug | HTTP application error handler | `500` with the same safe service text | Show the service error and retain draft | Log the exception on the server for diagnosis |

The content safeguard is **not implemented**. Today the backend checks reply structure and the
two-question cap; it cannot reliably reject invented facts, diagnoses, prompt leakage, or other
unsafe yet well-formed prose. Build and test specific response rules before claiming those cases
are blocked. Until then, review real model replies manually against the
[acceptance rules](test-cases.md#acceptance-rules-for-model-written-text). Structurally valid but
nonsensical owner text is not automatically a `422`.

## HTTP contract

`POST /v1/chat` accepts the existing `TurnRequest` shape: `intake` plus the complete, current
`history`. A successful response is `{ "reply": "...", "kind": "question|summary|emergency_notice",
"run_id": null }` until tracking is added. Later, `run_id` holds the recorded run ID. The fixed
summary suffix and emergency notice still come from `workflow.py`.

Normalize both request-schema errors and `InvalidTurnRequest` to a clear `422` shape, for example:

```json
{
  "error": "Please correct the request and try again.",
  "issues": [{"field": "intake.concern", "message": "Enter a concern."}]
}
```

Use `field: "history"` for a history-order or length error. Include no echoed owner text. The
desktop displays the issue beside the relevant field or as a chat-history error. The HTTP layer
must handle both FastAPI/Pydantic request validation and the workflow's `InvalidTurnRequest`;
handling only one leaves the other with a different response format.

Every `ModelOutputError` and future safeguard rejection maps to exactly this public `503` body:

```json
{
  "error": "The assistant could not complete this response. Please try again or contact a veterinarian if concerned.",
  "run_id": null
}
```

`run_id` becomes a string when a failure run was recorded. Keep `failure_reason`, `parse_failure`,
provider exception type, stack trace, and rejected reply in backend logs/tracking only. If the
desktop receives an unexpected error body, it displays its own copy of the same fixed service text
rather than raw HTTP content. The desktop may show a separate connection message when there was no
HTTP response at all. An unexpected `500` uses the same JSON shape and wording, with `run_id: null`
if no run was recorded.

The adapter currently calls LangChain structured output, which may raise during parsing before
`workflow._ask_model` can validate a raw reply. When implementing this contract, classify those
known parse/validation failures as `invalid_model_output` as well; do not mislabel case C4 as a
generic provider failure. All of these reasons still produce the identical public `503` text.

## Desktop turn state and manual retry

Keep the last **accepted** question-and-answer pairs separately from the draft answer to the
currently displayed question. On Send, build one request snapshot from the intake, accepted pairs,
current question, and draft answer. For the first turn, send the intake with empty history. While
the request is pending, show a pending state and prevent another Send. Do not add the draft pair to
accepted history until the backend returns a successful `question` or `summary`.

On `422`, leave the text editable and show the validation issue. On `503`, `500`, or connection
failure, leave the exact answer visible and enable **Try again**. If the owner edits it, the next
request uses the edited value. A successful `question` commits the submitted pair, displays the
new question, and clears only the answer box. A successful `summary` or `emergency_notice` ends the
chat and offers **New concern**; neither is sent back as history. Ignore a late response from an
abandoned request so it cannot advance the chat after the owner has started a new concern.

**Try again** is a new, owner-initiated call with the same current chat state. It may receive a
different model response. A timeout or broken connection also leaves the result of the first call
unknown to the desktop. Once MLflow tracking exists, manual retries can create separate turn runs;
do not imply exactly-once recording. Automatic retry remains disabled until there is an explicit
idempotency design covering a stable request ID, concurrent duplicate requests, stored outcomes,
replaying the original response, and one tracking record per logical turn.

## Where the next implementation goes

| File | Work |
| --- | --- |
| `src/backend/app.py` | Implement `POST /v1/chat`, request/error handlers, fixed service text, and `GET /health`. Convert both kinds of `422` and all `ModelOutputError` reasons to the contracts above. |
| `src/backend/schemas.py` | Reuse existing request, result, and error types; add a safeguard failure reason only when a response rule is actually implemented. Keep diagnostic reasons internal and correct the current `ModelOutputError` docstring, which says HTTP will report them. |
| `src/backend/workflow.py` | Keep validation, emergency bypass, one model call, shape check, and question cap. Add future response checks after shape validation and before returning any model text. |
| `src/backend/model.py` | Preserve one provider invocation and classify provider parse errors correctly. No fallback model call. |
| `src/frontend/api_client.py` | Use asynchronous Qt HTTP, distinguish `422`, `503`, and no-response failures, and never retry automatically. |
| `src/frontend/app.py` | Hold draft/accepted-history state, pending state, visible errors, **Try again**, and **New concern**. |
| `src/backend/tracking.py` (later) | Record one attempt and its internal reason when available. A write failure cannot change the chat outcome. |

For interactive testing, make the backend log only the stage and decision (request accepted,
history accepted, emergency match or miss, model mode, provider success/failure, reply accepted or
rejected, HTTP status). Keep owner-entered text and raw model failures out of routine logs. The
desktop shows the current state and result; these backend events let a tester see where a turn
stopped without exposing diagnostics to the owner.

## Acceptance checks before manual chat testing

- API tests with a fake model: C1/C6 return `422` with a useful issue and zero model calls;
  C3/C4/C5 return the exact same `503` body and never display model text. Test a `200` question,
  summary, and emergency notice as controls.
- Desktop client/state tests: D1-D4 retain the draft on failure, allow only a manual retry, advance
  history only on success, and end the chat after summary/emergency notice.
- When a response safeguard is added, test a well-formed rejected reply at the workflow and HTTP
  boundaries. It must produce the same fixed `503`, with no rejected text in the response.
- Run a real local Ollama chat with a few [synthetic cases](test-cases.md): ordinary concern with
  zero and two follow-ups, an emergency phrase, malformed input, and an Ollama-unavailable case.
  Check the displayed result and backend stage log for each turn. Review ordinary model wording by
  hand; passing the HTTP tests does not establish that the model's prose is medically sound.
