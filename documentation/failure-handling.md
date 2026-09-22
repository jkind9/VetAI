# Failure handling

This document defines what the backend and desktop do for every known outcome in the multi-chain
conversation. It distinguishes correction, deterministic continuation, manual retry, and terminal
success. It also states explicitly when the application does **not** retry, rephrase, or invent a
fallback.

## Global policy

- No automatic model retry.
- No automatic second web search.
- No alternative model or provider fallback.
- No model-written default medical response.
- No automatic rephrasing after a technical failure.
- A model/search/synthesis failure returns one stable `503` message and preserves the current owner
  answer for a user-initiated **Try again**.
- Invalid input or history returns `422` and asks for correction without calling downstream stages.
- A deterministic emergency match returns the fixed `200 emergency_notice` and ends the chat.
- Individual unusable search results may be discarded while other results from the same completed
  search are used. That is filtering, not a retry.

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
| First adaptive chain returns `ready_for_search` instead of a question | Required-question contract is violated | `503`; retain draft and offer **Try again** | No | No silently substituted question |
| Adaptive chain returns malformed/blank/overlong output | Structured output rejected | `503`; retain draft and offer **Try again** | No | Invalid text is never displayed |
| Adaptive model times out | Model adapter raises `timeout` | `503`; retain draft and offer **Try again** | No | No default question |
| Ollama is unreachable | Model adapter raises `connection` | `503`; retain draft and offer **Try again** | No | No alternative model |
| Other adaptive model/provider failure | Model adapter raises `model_call_failed` | `503`; retain draft and offer **Try again** | No | No automatic rephrasing |
| Adaptive chain asks beyond three adaptive questions | Workflow refuses a fourth question and proceeds only after the third answer | No fourth question is displayed | No | Search path is selected by the workflow |
| Search-query chain returns malformed, empty, overlong, or unsafe queries | Query plan is rejected before external access when possible | `503`; retain draft and offer **Try again** | No | Raw transcript is never substituted as a query |
| Search query contains a URL, email address, phone-like value, or other blocked personal/contact pattern | Privacy validator stops before network access | `503`; retain draft and offer **Try again** | No | No weakened query or transcript fallback |
| Search provider times out, is unreachable, rate-limits, or fails | Search stage stops | `503`; retain draft and offer **Try again** | No | No unsourced assessment |
| Search result URL is HTTP, off-list, malformed, or redirects off-list | Discard that result | Continue with other approved results from the same search | No | The rejected result is never passed to the model |
| One approved page cannot be fetched or parsed | Discard that page | Continue only if approved evidence remains | No | Search snippet may be used only if the search adapter explicitly marks it as evidence |
| No usable approved evidence remains | Synthesis is not called | `503`; retain draft and offer **Try again** | No | No model-only possible causes |
| Synthesis returns invalid structure, blank required sections, unknown source IDs, or an uncited possible area/observation | Grounding validation rejects the result | `503`; retain draft and offer **Try again** | No | Invalid or ungrounded text is never displayed |
| Synthesis model times out or is unreachable | Model adapter stops the turn | `503`; retain draft and offer **Try again** | No | No partial assessment |
| Unexpected backend exception | Exception is logged without owner text | `500`; same safe service message | No | No raw exception details |
| Desktop cannot reach the API | No HTTP response | Keep current answer; show connection error and **Try again** | No | No assumption that server did or did not finish |
| Desktop request times out | Outcome may be unknown | Keep current answer; show timeout and **Try again** | No | Retrying creates a new attempt |
| A vague but valid owner answer is supplied | It is accepted as owner text | Continue; the adaptive chain may clarify within its cap | No | No fabricated detail |
| Successful question | Commit the submitted pair | `200 question`; show next assistant bubble | Not applicable | No extra text |
| Successful assessment | Validate citations, append fixed disclaimer, end chat | `200 assessment`; show structured sections and **New concern** | Not applicable | Only retrieved sources are displayed |

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

Internal stage/reason values are for logs and future MLflow traces only. The API never returns raw
provider exceptions, owner text, generated queries, rejected model output, or retrieved excerpts.

## Draft and history behaviour

The desktop keeps accepted question/answer pairs separate from the answer being submitted. A pair
is committed only after a successful question or assessment. While a request is pending, the owner
answer may be shown as a pending bubble and the composer is disabled. On failure, the bubble is
marked failed or removed and the exact answer remains in the composer. **Try again** submits the
same current state unless the owner edits it.

An emergency notice or assessment ends the chat. A late response from an abandoned request is
ignored by request ID. **New concern** clears the intake, history, pending state, and bubbles.

## Time budgets

The final request can contain query generation, external search, and synthesis, so it has a longer
desktop timeout than an ordinary question turn. Each network/model component still owns a bounded
timeout. Reaching any budget is a failure, not permission to skip grounding or return a partial
assessment.

Exact launch defaults live in backend settings and are documented in `config/README.md`.
