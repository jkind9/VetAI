# Failure handling

This document defines what the backend and both clients do for every known outcome in the
multi-chain conversation. It distinguishes correction, deterministic continuation, manual retry,
and terminal success. It also states explicitly when the application does **not** retry, rephrase,
or invent a fallback.

## Global policy

- No automatic model retry.
- The search adapter repeats the same generated plan once only when every provider call in its first
  attempt fails. It never asks the model to rephrase, replan, or choose another search client.
- If any provider call completes but the plan returns no raw results, that is a named
  `no_search_results` outcome, even if a sibling call failed. It does not qualify for a repeat.
- No alternative model or application-level search client after a failure. The configured `ddgs`
  client uses its `auto` mode, which may try more than one engine inside that single search call.
- No model-written default medical response.
- No automatic rephrasing after a technical failure.
- A model/search/synthesis failure returns one stable `503` message and preserves the current owner
  answer for a user-initiated **Try again**.
- Invalid input or history returns `422` and asks for correction without calling downstream stages.
- A deterministic emergency match returns the fixed `200 emergency_notice` and ends the chat.
- An adaptive-model `urgent_escalation` returns that same fixed notice. The model chooses the route,
  not owner-visible wording, and no later query/search/synthesis stage runs.
- Individual unusable search results may be discarded while other results from the same completed
  search are used. That is filtering, not a retry.
- A failed query does not discard raw results returned by another query in the same plan.
- Every turn is recorded as an MLflow run, and recording never changes the reply. If MLflow cannot
  open a run, the turn is answered anyway, untraced, with `run_id: null`, and the error is logged.
  Any later MLflow write that fails is logged and skipped. A deleted experiment is restored when
  the server starts.

“Ask the same thing another way” is not a hidden recovery path. It would be another owner-visible
model call and is deferred with post-result follow-ups. If a structured chain output is malformed,
the owner sees the stable service error; the application never displays the malformed text.

## Backend error and action matrix

| Condition | Stage and internal outcome | HTTP / owner action | Automatic retry? | Default, fallback, or alternative phrasing? |
| --- | --- | --- | --- | --- |
| Missing species or concern, unsupported species, blank concern, or overlong concern | Request validation stops before workflow | `422`; correct the named field | No | Field-specific correction only |
| Blank or overlong answer | Request validation stops before workflow | `422`; edit the answer | No | Input correction only |
| Odd, out-of-order, over-12-message, or otherwise malformed history | History validation stops | `422`; correct/restart the chat | No | Stable history correction message |
| First three assistant messages do not match the standard question catalog | History validation rejects a skipped/altered prefix | `422`; restart/correct history | No | No inferred replacement history |
| Curated warning phrase in any owner answer | Emergency gate returns fixed result and skips every later stage | `200 emergency_notice`; contact an emergency veterinarian | No | Fixed application wording only |
| Standard-question phase | Workflow returns the next catalog question | `200 question`; owner answers it | Not applicable | Deterministic catalog wording |
| Adaptive model recognises urgent context that phrase matching missed, including misspelling | Workflow returns the fixed emergency result and skips every later stage | `200 emergency_notice`; contact an emergency veterinarian | No | Same fixed application wording; model text is never displayed |
| First adaptive chain returns `ready_for_search` instead of a question | Required-question contract is violated | `503`; retain draft and offer **Try again** | No | No silently substituted question |
| Adaptive chain returns malformed/blank/overlong output | Structured output rejected | `503`; retain draft and offer **Try again** | No | Invalid text is never displayed |
| Adaptive model times out | Model adapter raises `timeout` | `503`; retain draft and offer **Try again** | No | No default question |
| Ollama is unreachable | Model adapter raises `connection` | `503`; retain draft and offer **Try again** | No | No alternative model |
| Other adaptive model/provider failure | Model adapter raises `model_call_failed` | `503`; retain draft and offer **Try again** | No | No automatic rephrasing |
| Three adaptive questions have been answered | The workflow goes straight to search without calling the model | Continue to search | No | The code counts the questions, so the model is never asked for a fourth |
| Search-query chain returns malformed, empty, overlong, or unsafe queries | Query plan is rejected before external access when possible | `503`; retain draft and offer **Try again** | No | Raw transcript is never substituted as a query |
| Search query contains a URL, email address, phone-like value, or other blocked personal/contact pattern | Privacy validator stops before network access | `503`; retain draft and offer **Try again** | No | No weakened query or transcript fallback |
| One planned query times out, is unreachable, rate-limits, or fails, while another returns raw results | Keep the returned raw results and continue allowlist/fetch validation | Continue if usable approved evidence remains | No additional retry | No unsourced assessment |
| Every planned provider call times out, is unreachable, rate-limits, or fails | Repeat the exact generated plan once; after a second total failure raise `search_failed` | `503`; retain draft and offer **Try again** | One bounded repeat only | No unsourced assessment, rephrasing, or provider swap |
| At least one provider call completes but the plan returns no raw results, including when a sibling call fails | Raise `no_search_results`; synthesis is not called | `503`; retain draft and offer **Try again** | No | No unsourced assessment |
| Search result URL is HTTP, off-list, malformed, or redirects off-list | Discard that result | Continue with other approved results from the same search | No | The rejected result is never passed to the model |
| One approved page cannot be fetched or parsed | Discard that page | Continue only if approved evidence remains | No | Search snippet may be used only if the search adapter explicitly marks it as evidence |
| Raw results exist but no usable approved evidence remains | Raise `insufficient_evidence`; synthesis is not called | `503`; retain draft and offer **Try again** | No | No model-only possible causes |
| Synthesis returns invalid structure, contradictory outcome/possible areas, blank required sections, unknown source IDs, or an uncited possible area/action | Grounding validation rejects the result | `503`; retain draft and offer **Try again** | No | Invalid or ungrounded text is never displayed |
| Synthesis model times out or is unreachable | Model adapter stops the turn | `503`; retain draft and offer **Try again** | No | No partial assessment |
| Unexpected backend exception | Exception is logged without owner text | `500`; same safe service message | No | No raw exception details |
| Client cannot reach the API | No HTTP response | Keep current answer; show connection error and **Try again** | No | No assumption that server did or did not finish |
| Client request times out | Outcome may be unknown | Keep current answer; show timeout and **Try again** | No | Retrying creates a new attempt |
| A vague but valid owner answer is supplied | It is accepted as owner text | Continue; the adaptive chain may clarify within its cap | No | No fabricated detail |
| Successful question | Commit the submitted pair | `200 question`; show next assistant bubble | Not applicable | No extra text |
| Successful assessment | Validate outcome and citations, build the labelled recap from owner-authored input, add fixed outcome wording and disclaimer, end chat | `200 assessment`; show structured sections and **New concern** | Not applicable | The model cannot author the recap or outcome notices; only retrieved sources are displayed |

## Public HTTP contracts

Validation failures use:

```json
{
  "error": "Please correct the request and try again.",
  "issues": [{"field": "history", "message": "Correct the chat history and try again."}]
}
```

Every handled model, query, search, evidence, or synthesis failure uses:

```json
{
  "error": "The assistant could not complete this response. Please try again or contact a veterinarian if concerned.",
  "run_id": null
}
```

Internal stage/reason values go only to the server log and to the turn's MLflow run, as the
`failed_stage` and `failure_reason` tags. The API never returns raw
provider exceptions, owner text, generated queries, rejected model output, or retrieved excerpts.

## Draft and history behaviour

Both clients keep accepted question/answer pairs separate from the answer being submitted. A pair
is committed only after a successful question or assessment. While a request is pending, the owner
answer may be shown as a pending bubble and the composer is disabled. On failure, the bubble is
marked failed or removed and the exact answer remains in the composer. **Try again** submits the
same current state unless the owner edits it.

An emergency notice or assessment ends the chat. A late response from an abandoned request is
ignored by request ID. **New concern** clears the intake, history, pending state, and bubbles.

## Time budgets

The final request can contain query generation, external search, and synthesis, so clients allow a
longer timeout than an ordinary question turn. Each network/model component still owns a bounded
timeout. Reaching any budget is a failure, not permission to skip grounding or return a partial
assessment.

Exact launch defaults live in backend settings and are documented in `config/README.md`.

## Test mapping

- `tests/test_api.py` covers validation/history correction and successful public response shapes.
- `tests/test_error_contracts.py` exercises malformed model output, timeout, search failure, empty
  evidence, malformed/ungrounded synthesis, and unexpected `500` handling at the HTTP boundary.
- `tests/test_workflow.py` proves phrase and model escalation short-circuit later stages, including
  the typo case and the final cap decision.
- `tests/test_search.py` covers deterministic allowlist/filtering failures, retained sibling
  results, the bounded total-failure repeat, and named no-result/no-evidence outcomes; the opt-in
  `tests/test_approved_source_smoke.py` covers a real approved page.
- `src/frontend/public/e2e/full-process.spec.js` proves the hosted browser preserves a failed draft,
  exposes manual retry, and successfully resubmits the same answer.

Workflow retry-boundary assertions use stage-aware fakes. Search-adapter tests use scripted provider
outcomes to prove that a completed empty result is not repeated and that only a total provider
failure is repeated once.
