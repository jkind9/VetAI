# Test cases

Each case below is an example conversation and the reply the app must give. They define what
"working" means, and the tests check them. They are made-up examples: passing them does not make
the app clinically safe, and a case that isn't flagged is not proof that a pet is fine.

Most cases run in the ordinary test suite (`uv run pytest`). Those tests use a stand-in model and
fake search results, so they need no Ollama, no internet, and no screen. Section J is different:
those cases run whole chats against the real model and live web search, and are switched on by
hand.

Terms used below:

- **follow-up question**: one of the one to three questions the model writes after the three
  standard questions (called "adaptive" in the code);
- **summary**: the final result, with its sources (called the "assessment" in the code, and
  "synthesis" for the model step that writes it);
- **phrase list**: the fixed emergency warning phrases checked in plain Python.

## Rules every conversation follows

- The form asks for species and concern only.
- The chat history holds zero to six question-and-answer pairs.
- The first three questions match the standard questions word for word.
- At least one and at most three follow-up questions are answered before search.
- On every message, the phrase list checks the owner's own words (the concern and every answer).
- If the phrase list doesn't match, the model emergency check runs next, before any question or
  search. It is the only model step that can raise an emergency.
- The follow-up step can only ask a question or say it has enough. The code stops it after three.
- Search receives the generated queries, never the chat itself.
- A summary or an emergency notice ends the chat.

## S: standard questions

| ID | Input | Expected |
| --- | --- | --- |
| S1 | Dog, "My dog scratched one ear today", no history; emergency check says no | The emergency check runs once, then the first standard question ("How long has this been happening?"). No other model step or search |
| S2 | S1 plus the answer "Since this morning"; emergency check says no | The emergency check runs once on the whole history, then the second standard question. No other model step or search |
| S3 | Two standard questions answered; emergency check says no | The emergency check runs once, then the third standard question |
| S4 | The first question in the history isn't the standard wording | `422` on `history`. No model call or search |
| S5 | An answer is blank or over 1,000 characters, a question has no answer, or the roles are swapped | `422`. No model call or search |

## A: follow-up questions and the limit

| ID | Input, and what the stand-in model does | Expected |
| --- | --- | --- |
| A1 | Three standard questions answered; the model asks a question | That question is returned. The model can't start search yet |
| A2 | One follow-up answered; the model says it has enough | Search queries, then search, then the summary |
| A3 | One follow-up answered; the model asks another | The question is returned. No search |
| A4 | Two follow-ups answered; the model asks a third | The question is returned. No search |
| A5 | Three follow-ups answered | The emergency check still runs. If it says no, the model isn't asked for a question: search starts |
| A6 | First follow-up: the model says it has enough | `503`. No search and no made-up question. The owner can press **Try again** |
| A7 | The model's reply is malformed, blank, or too long | `503`. Nothing retried, and the broken reply is never shown |
| A8 | The model tries to raise an emergency from the follow-up step | Rejected as a malformed reply: `503`, no search. Only the emergency check can raise an emergency |
| A9 | One follow-up answered; the model repeats an earlier question word for word (ignoring capitals) | Treated as "I have enough": search starts. The repeat is never shown |
| A10 | One follow-up answered; the model asks about the pet's age again in different words (both questions mention "age" or "how old") | Treated as a repeat: search starts |
| A11 | First follow-up: the model repeats a question | `503`, because at least one new follow-up is required |

## R: search queries and approved sources

| ID | Input | Expected |
| --- | --- | --- |
| R1 | A valid plan: one to three short, neutral queries, at least one asking whether the sign is normal or worrying | Search runs only after at least one follow-up. It receives the queries, never the chat, and keeps at most three results per query |
| R2 | A query contains a web address, an email address, or a phone number, or is too long | Rejected before anything is sent: `503`, the owner's answer is kept |
| R3 | Results from `vet.cornell.edu` and `example.com` | The Cornell result is kept; the other is dropped |
| R4 | A result uses `http://`, is malformed, is a lookalike such as `aspca.org.example.com`, or redirects off the list | Dropped |
| R5 | The same approved page comes back from two queries | Sent to the summary once |
| R6 | One approved page fails to download and another works | Carry on with the one that worked. No new search |
| R7 | One query fails and another returns an approved result | Keep that result and carry on |
| R8 | Every query fails | The same queries are sent again after 1, 2 and 4 seconds. If all fail, the summary goes ahead without sources and shows the search notice. No rewording and no other search service |
| R9 | At least one query worked, but nothing came back at all | No retry; the summary goes ahead without sources and shows the search notice |
| R10 | Results came back, but no page passed the checks | The summary goes ahead without sources and shows the search notice |
| R11 | Opt-in live check: download the MSD Veterinary Manual's dog-or-cat emergency page | The address and any redirect stay on the approved list, and the page text contains "heat stroke", "rapid panting" and "water" |
| R12 | Every query keeps failing slowly | A new attempt starts only if, judging by the last attempt's time, it should finish within 20 seconds of search time, so the turn stays inside the screens' 65-second limit |
| R13 | The search code raises an unexpected error (a bug, not an outage) | `503`. No summary |
| R14 | One result has a title over 300 characters | That result is skipped; the other pages are used |

## G: the summary and its citations

| ID | Input, and what the stand-in model writes | Expected |
| --- | --- | --- |
| G1 | "Possible problem", with every item citing pages `S1` and `S2` that were read | The summary is returned. The app adds the outcome wording and builds the source list |
| G2 | Pages were found, but a point or suggested action cites none | `503` |
| G3 | The model cites `S99`, a page that wasn't read | `503`. The made-up citation is never shown |
| G4 | The model tries to supply a link or title | Not possible: the reply shape has no field for them. The app builds the links |
| G5 | The summary step is malformed, blank, times out, or fails | `503`. No retry and no partial summary |
| G6 | "Possible problem" with no points for the vet, or "nothing flagged" with some | `503` |
| G7 | A valid "nothing flagged" summary | The fixed "this is not an all-clear" wording, at least one cited suggested action, at least one cited question for the vet, and the sources |
| G8 | Any successful summary | Shows the outcome and its fixed wording, what the owner reported, points for the vet (only for "possible problem"), suggested actions, questions for the vet, sources, and the fixed disclaimer. The chat ends |
| G9 | The model tries to write the "what you reported" section | Rejected. The app builds that section from the owner's own words |
| G10 | gpt-oss names an item's text field `area`, `action` or `question` instead of `text` | Those three names are accepted as `text`, and the whole reply is checked again. Any other wrong field is still rejected |
| G11 | No usable pages were found; the model writes items from general guidance (the prompt asks for the placeholder ID `"none"`, which the app drops) | The summary is returned with no sources and the notice "The source search did not work, so this result is based on general guidance and has no linked sources." |
| G12 | Pages were found; the model adds widely accepted general guidance that fits the report, citing the most relevant page | Accepted |

## E: emergencies

| ID | Input | Expected |
| --- | --- | --- |
| E1 | Concern: "My dog is struggling to breathe." | The fixed emergency notice. No model call or search |
| E2 | Concern: "My dog collapsed just now." | The same notice |
| E3 | Concern: "My dog may have swallowed a medication." | The same notice |
| E4 | Concern: "My cat cannot urinate." | The same notice |
| E5 | Any later answer contains a warning phrase | The notice on that message. Nothing after it runs |
| E6 | The app's own question contains warning words, and the owner answers "No" | The app's questions are never checked, so the chat carries on |
| E7 | Near misses: "Maybe a week", "trying to wait a week", "her heart rate went up after her new medication", and denials | No phrase-list match: "wee" inside "week" and "ate" inside "rate" aren't whole words. This doesn't mean the pet is fine |
| E8 | Concern: "My dog is dieing" (misspelled, so the phrase list misses it); the emergency check says yes on the first message | The same notice, before any standard question. No other model step or search |
| E9 | The third follow-up answer is urgent but worded in a way the phrase list misses; the emergency check says yes | The same notice. Search never starts |
| E10 | No phrase match, and the emergency check says no on messages 1, 2 and 3 | The check runs exactly once per message, then the next standard question |
| E11 | A phrase match on any message | The model check isn't called |
| E12 | Opt-in live check: seven clear emergencies the phrase list misses (such as "She can't breathe" with a curly apostrophe, "Max collapsed on the kitchen floor", "Her tongue has gone blue") and seven ordinary statements (such as "maybe a week", "she isn't having any trouble breathing"), sent straight to the real model check | All 7 emergencies flagged, none of the ordinary statements. One MLflow run records `emergencies_caught`, `false_alarms` and `cases`. Before this check existed, the follow-up step caught 2 of the 7 |

## F: failures and the API

| ID | What goes wrong | Expected |
| --- | --- | --- |
| F1 | Invalid form or history | `422` naming the field. Nothing after it runs |
| F2 | The model times out | The fixed `503` text. The owner's answer is kept; retrying is the owner's choice |
| F3 | Ollama can't be reached, or fails | The same `503`. No other model and no default text |
| F4 | Any model step returns a malformed reply | The same `503`. No attempt to repair it |
| F5 | Search fails or finds no usable pages | Not an error: the summary goes ahead without sources, with the search notice |
| F6 | An unexpected error | `500` with the same text. Details stay in the server log |
| F7 | MLflow recording | A successful reply includes its MLflow `run_id`; `503` and `500` replies have `run_id: null`, and `422` replies have no `run_id`. Every failed turn's run is marked FAILED with a `failure_reason` (and `failed_stage` for model, search and citation failures). If MLflow can't open a run, the reply still goes out. A failed MLflow write never changes the reply. A deleted experiment is restored when the server starts |
| F8 | Three follow-ups answered | The emergency check still runs, but the model isn't asked for a question, so it can't add a fourth or send a malformed one |
| F9 | The project folder's path contains a space or `&`, and `MLFLOW_TRACKING_URI` isn't set | Runs are saved to `mlflow.db` in the folder the backend was started from, the same file `uv run mlflow ui` reads. A set `MLFLOW_TRACKING_URI` is always respected |

## D: desktop window

| ID | Action | Expected |
| --- | --- | --- |
| D1 | Send a valid concern | The concern appears at once as a right-hand owner bubble, with a "Thinking…" bubble. The request has an empty history |
| D2 | A question comes back | "Thinking…" goes away, the question appears as a left-hand bubble, and the answer box is ready |
| D3 | An answer is accepted | It appears as its own owner bubble. It joins the history only after the backend accepts it |
| D4 | The request fails | The typed answer stays in the box, with the error and **Try again**. No duplicate bubble |
| D5 | A summary comes back | Outcome wording, what was reported, points for the vet (if any), suggested actions, questions for the vet, and clickable sources. Input is locked and **New concern** appears |
| D6 | **New concern** | Every bubble, the form, the history, errors and "Thinking…" are cleared |
| D7 | A reply arrives after **New concern** | Ignored |
| D8 | The very first request fails | The species and concern stay editable, and **Try again** sends them again |
| D9 | A concern or answer is over 1,000 characters | Refused with a message, never cut short, because the cut-off end might contain a warning phrase |
| D10 | The backend replies `422` or `503` | The backend's own message is shown, not "could not reach the assistant" |

## W: browser page and whole chats

| ID | Scenario | Expected |
| --- | --- | --- |
| W1 | The page hasn't been built (`src/frontend/public/dist` is missing) | The backend still starts, and the API works |
| W2 | The page has been built | `/` serves the page, and `/health`, `/v1/chat` and `/docs` still work |
| W3 | The owner answers all three standard and all three follow-up questions; the outcome is "possible problem" | The built page sends every message to a real backend and shows the full summary with sources, the disclaimer and **New concern** |
| W4 | The same, with the outcome "nothing flagged" | The page shows the "not an all-clear" wording, suggested actions, sources, the disclaimer and **New concern**, with no "points for the vet" section |
| W5 | The first concern matches a warning phrase | The fixed notice comes back at once; the answer box goes and **New concern** appears |
| W6 | The concern is misspelled ("dieing") so the phrase list misses it, and the emergency check says yes | The page shows the full fixed notice and **New concern** |
| W7 | The follow-up step fails after the third standard answer | The page shows the error and **Try again**, and keeps the exact typed answer |
| W8 | The source search fails | The page shows the summary with the search notice, and no citations or "Sources" heading |

W3 to W8 run in a real browser (Playwright) against a real backend and the built page, with the
stand-in model and fake search. The real model and live search are tested separately, so an
outside service being down can't make this suite fail. Known gap: in the browser, **Try again**
doesn't yet work when the very first request fails (the desktop's D8 does).

## J: whole chats with the real model

These run the real app, the real model (gpt-oss:20b by default) and, when a chat reaches search,
live web search. They are switched on by hand:

```powershell
$env:VETAI_RUN_LIVE_E2E = "1"
uv run pytest tests/test_live_customer_journeys.py -v -s
```

A chat only counts if it uses:

- the real backend, through `POST /v1/chat` or the built browser page;
- the real model for every model step, with no scripted replies;
- live search on the approved sites, whenever the chat reaches search;
- a fresh chat, sending the history each time exactly as a real client would.

Each run writes a JSON record under `artifacts/live-journeys/` (not committed), and each message is
also recorded in MLflow. The record holds the model, every reply, the generated questions and
queries, the sources, the timings and any failures. Use made-up details only.

The exact wording the model writes isn't checked automatically. The tests check the structure, the
route taken, the citations and the safety rules. A person then reviews each J3 and J4 record
against the [review rules](#human-review-rules). Run J2, J3 and J4 three times each and report
every run, not just the best. A safe `503` is correct behaviour, but it counts as a failed run.

### J1: warning phrase

| Step | Input and expected result |
| --- | --- |
| Start | Dog, "My dog is struggling to breathe.", no history |
| Expected | `200` with the fixed emergency notice on the first message |
| Check | Nothing after the phrase list ran. The turn's MLflow trace names the rule (`breathing_difficulty`) and has no model or search steps |
| Fails if | A question is asked, the wording differs, a model or search step runs, or the chat doesn't end |

### J2: the model emergency check

The misspelling "dieing" isn't in the phrase list, so only the real model can flag it.

| Step | Input and expected result |
| --- | --- |
| Start | Dog, "I think my dog is dieing and getting worse." |
| Expected | `200` with the same fixed notice, before any standard question |
| Check | The phrase list didn't match, the model check ran once, and no other model step or search ran |
| Fails if | The phrase list claims the match, a standard question is asked, model-written emergency wording is shown, or the chat doesn't end |

### J3: a full chat to a summary

The owner's facts, used to answer every question. Don't add symptoms to steer the model.

- The dog has panted more than usual while resting since yesterday evening.
- It hasn't happened before, and it comes and goes.
- The dog settles when asleep, is walking, eating and drinking, and has pink-looking gums.
- No hard exercise or medication; the room has been warm.
- No vomiting, but the dog seems a little more tired than usual.

| Step | Input and expected result |
| --- | --- |
| Start | Dog, "My dog has been panting more than usual while resting." |
| Standard answers | "Since yesterday evening."; "No, this is the first time."; "It comes and goes while resting." |
| Follow-ups | The model asks one to three relevant questions that don't repeat. Answer from the facts above |
| Queries | One to three short, neutral queries, with no personal details or invented facts. At least one asks whether the sign is normal or worrying |
| Search | Live search keeps only approved HTTPS pages and finds at least one about panting |
| Summary | `200` with "possible problem" or "nothing flagged", the fixed wording, what was reported, cited suggested actions and vet questions, sources and the disclaimer |
| Fails if | An emergency is raised without cause, no follow-up is asked, search is skipped, no approved page is found, the summary step fails, a citation is missing or invented, or unsafe advice is shown |

### J4: an all-normal chat

This checks that pages about illnesses don't push an ordinary case towards "possible problem". Use
the exact wording below, and answer every follow-up with "no".

| Step | Input and expected result |
| --- | --- |
| Start | Dog, "My dog is breathing completely normally" |
| Standard answers | "forever"; "yes, its always been normal"; "constantly normal" |
| Follow-ups | One to three questions that don't repeat, each answered "no" |
| Queries and search | At least one query asks whether the sign is normal or worrying, and approved pages are found |
| Summary | `200`, "nothing flagged", and no points for the vet |
| Check | "What you reported" matches the owner's words exactly, with nothing copied from the pages |
| Fails if | An emergency or "possible problem", any point for the vet, an invented fact, a `503`, skipped search, an unsafe query, or an unapproved source |

### Latest results

| Case | Result | Notes |
| --- | --- | --- |
| J1 | Passed | |
| J2 | 3 of 3 passed | Run with llama3; to be repeated with gpt-oss:20b |
| J3 | 2 of 3 passed | gpt-oss:20b; both passing runs passed human review. The third hit a search-service outage: the app still returned a summary with the "search did not work" notice, but J3 requires real sources |
| J4 | 3 of 3 passed | gpt-oss:20b; all three passed human review |

The J3 and J4 records were first checked by an AI reviewer against the rules below. The project
owner then reviewed each record against the same rules on 28 September 2026.

## Human review rules

A real-model chat passes review only when:

1. each follow-up is one relevant question that doesn't ask for something already answered;
2. the search queries are short and neutral, with no personal or contact details;
3. "what you reported" matches the owner's words exactly, with nothing added by the model;
4. points for the vet are broad, not ranked, and cite pages that were read;
5. suggested actions cite pages and stick to watching, recording, or simple low-risk steps: no
   medicines, doses, invasive steps, unproven remedies, forcing food or water, specific tests, or
   advice to put off seeing a vet;
6. nothing says the pet is safe, normal, definitely has a condition, or doesn't need a vet;
7. every source shown is an approved page that was actually read.

The live source check (R11) only proves one approved page can be downloaded; it doesn't replace
J3:

```powershell
$env:VETAI_RUN_LIVE_SEARCH_SMOKE = "1"
uv run pytest tests/test_approved_source_smoke.py -v
```
