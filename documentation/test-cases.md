# Behavioural test cases

These synthetic cases define the multi-chain software contract. They are not diagnoses, clinical
validation, or evidence that an unmatched concern is safe. Normal automated tests use fake chain
and search objects; no ordinary test needs Ollama, internet access, or a display.

## Conversation invariants

- Initial intake contains species and concern only.
- Active history is zero to six complete assistant-question/owner-answer pairs.
- The first three assistant messages exactly match the standard question catalog.
- At least one and at most three adaptive questions are answered before search.
- Emergency matching is repeated on every request using owner-authored concern and answers only.
- Search receives generated queries only, never the raw transcript.
- An assessment or emergency notice ends the conversation.

## S — standard questions

| ID | Input | Expected behaviour |
| --- | --- | --- |
| S1 | Dog; concern “My dog scratched one ear today”; empty history | Return `question`, `question_type=standard`, ID `duration`, exact first catalog wording; zero model and search calls |
| S2 | S1 plus answer “Since this morning” | Return standard ID `previous_occurrence`; zero model and search calls |
| S3 | Two completed standard pairs | Return standard ID `pattern`; zero model and search calls |
| S4 | First assistant text differs from the duration catalog wording | `422 history`; zero model and search calls |
| S5 | Standard answer is blank, over 1000 characters, incomplete, or roles are reversed | `422`; zero model and search calls |

## A — adaptive questions and cap

| ID | Input / fake output | Expected behaviour |
| --- | --- | --- |
| A1 | Three standard pairs complete; fake adaptive chain asks a question | Return one `adaptive` question; one adaptive call; no search. The model is not allowed to end questioning yet |
| A2 | One adaptive pair complete; fake adaptive chain returns `ready_for_search` | Call query chain, then search, then synthesis; return structured assessment |
| A3 | One adaptive pair complete; fake asks a second question | Return question; no search |
| A4 | Two adaptive pairs complete; fake asks a third question | Return question; no search |
| A5 | Three adaptive pairs complete | Skip adaptive decision and force query → search → synthesis; never show a fourth adaptive question |
| A6 | First adaptive call returns `ready_for_search` | `503`; no search; no substitute question; owner can manually retry |
| A7 | Adaptive output is malformed, blank, or overlong | `503`; no automatic retry; raw output is hidden |

## R — query generation and approved-source retrieval

| ID | Input / fake output | Expected behaviour |
| --- | --- | --- |
| R1 | Valid plan with one to three neutral queries | Search occurs only after an adaptive answer; searcher receives the plan, not `TurnRequest` or raw history |
| R2 | Query contains an URL, email, phone-like value, or exceeds its limit | Reject before external search; return `503`; preserve draft |
| R3 | Results include `https://vet.cornell.edu/...` and `https://example.com/...` | Keep Cornell result; discard off-list result |
| R4 | Result uses `http://`, malformed URL, `aspca.org.example.com`, or an off-list redirect | Discard it |
| R5 | Duplicate approved URLs across queries | Supply one canonical evidence item to synthesis |
| R6 | One approved fetch fails and another succeeds | Continue with the usable item; do not rerun search |
| R7 | Search times out/fails or no approved evidence remains | `503`; synthesis is not called; no unsourced fallback |

## G — grounded synthesis

| ID | Input / fake output | Expected behaviour |
| --- | --- | --- |
| G1 | Valid sections cite retrieved IDs `S1` and `S2` | Return `assessment`; API sources are resolved from retrieved evidence, not model URLs |
| G2 | Possible area or observation has no source ID | Reject with `503` |
| G3 | Model cites unknown ID `S99` | Reject with `503`; do not display invented citation |
| G4 | Model tries to provide a URL/title different from evidence | Model shape does not accept URLs; workflow builds displayed sources |
| G5 | Synthesis is malformed, blank, times out, or fails | `503`; no automatic retry or partial result |
| G6 | Assessment succeeds | Include all five labelled sections plus fixed non-diagnostic wording; end chat |

## E — deterministic emergency route

| ID | Input | Expected behaviour |
| --- | --- | --- |
| E1 | Initial concern: “My dog is struggling to breathe.” | Fixed `emergency_notice`; zero model/search calls |
| E2 | Initial concern: “My dog collapsed just now.” | Same fixed notice |
| E3 | Initial concern: “My dog may have swallowed a medication.” | Same fixed notice |
| E4 | Initial concern: “My cat cannot urinate.” | Same fixed notice |
| E5 | Any standard or adaptive owner answer newly reports a curated warning phrase | Fixed notice on that request; no later chain/search call |
| E6 | Assistant question contains warning wording but owner says “No” | Do not scan assistant text; continue ordinary phase |
| E7 | Negated and near-miss cases from safeguard tests | Preserve existing matcher policy; do not imply general safety |

## F — failures and public API

| ID | Failure | Expected response/action |
| --- | --- | --- |
| F1 | Invalid intake/history | `422` with public field issue; no downstream calls |
| F2 | Model timeout | Fixed `503`; draft retained; manual retry only |
| F3 | Ollama connection/provider failure | Same `503`; no alternate model/default text |
| F4 | Invalid structured output at any chain | Same `503`; no automatic parse-repair call |
| F5 | Search failure/no evidence | Same `503`; no synthesis |
| F6 | Unexpected application exception | `500` with same safe service text; diagnostics stay in logs |
| F7 | Tracking not yet implemented | Successful responses continue to contain `run_id=null` |

## D — desktop behaviour

| ID | Action | Expected visible state |
| --- | --- | --- |
| D1 | Send a valid initial concern | Concern immediately appears in a right-aligned owner bubble; pending assistant state appears; request contains empty history |
| D2 | Successful standard/adaptive question | Pending state clears; left-aligned assistant bubble appears; composer is ready |
| D3 | Submit an answer successfully | Owner answer is visually separate; pair commits only after success |
| D4 | API/model/search failure | Exact draft remains editable; error and **Try again** appear; no duplicate accepted pair |
| D5 | Structured assessment | Five labelled sections and sources appear; input is disabled; **New concern** appears |
| D6 | New concern | All bubbles, intake, history, errors, and pending state clear |
| D7 | Late response after New concern | Ignore by request ID |

## Human review rules

Real-model output is acceptable only when:

1. each adaptive response is exactly one relevant question and does not repeat a known answer;
2. search queries are short, neutral, and disclose no obvious personal/contact data;
3. reported facts contain no invented symptom or timing;
4. possible areas are broad, non-ranked, and supported by valid retrieved IDs;
5. observation suggestions and veterinarian questions are informational, not treatment or test
   instructions;
6. no output says the pet is safe, normal, definitely has a condition, or does not need a vet;
7. every displayed source is an actually retrieved approved URL.

The later productionisation milestone will run a fixed scenario set against the chosen Ollama model
and live search. It remains separate from deterministic CI.
