# VetAI implementation plan

This is the plan the project started from, followed by the key points where it changed on the way
to what exists now. For how the app works today, read the [root README](../README.md) and the
[backend README](../src/backend/README.md).

## The initial plan

The brief asks for a simple AI pet triage built with LangChain and MLflow, and says it cares more
about the internals than the interface. The plan read "triage" narrowly: help an owner describe a
worry clearly and prepare for a vet visit. No diagnosis, no treatment advice, and no urgency
score, apart from a short list of warning phrases that send the owner straight to an emergency
vet.

It planned:

- **a desktop form and chat (PySide6)** asking for species, concern, how long it has been going
  on, whether it has happened before, and whether it is constant or comes and goes;
- **one LangChain chain** that either asks one follow-up question or writes a final recap, with at
  most two follow-ups, counted by code;
- **a recap of only what the owner said**, plus one or two points to raise with a vet;
- **a fixed emergency route**: plain Python checks the owner's words for warning phrases before
  any model call, and a match shows a fixed notice;
- **a FastAPI backend** that the desktop only talks to over HTTP;
- **MLflow saved to local files**: one run per chat turn, an evaluation run over fixed test cases,
  and a small command to print counts and response times;
- **supporting pieces**: a YAML settings file, a CI workflow, locked dependencies, and
  temperature 0 with a fixed seed.

```text
Desktop form -> POST /v1/chat -> check request -> emergency phrases?
                                          | yes: fixed emergency notice
                                          | no:  one LangChain + Ollama call
                                          v
                          one follow-up question OR the final recap
```

The principles behind it, all of which still hold except where noted:

- code enforces the rules and the model fills in the words;
- the model never writes the emergency notice;
- no automatic retries and no fallback answers (web search later became the one exception, below);
- no memory on the server: the screen sends the whole chat each time;
- tests use a stand-in model, so they need no Ollama or network;
- recording in MLflow never hides or changes a reply.

It deliberately left out a database, RAG, agents, urgency grades, a browser interface, and using a
second model to grade answers.

## How the plan evolved

**One chain became four, with web search.** To show chains working together, and to base the
result on real veterinary pages instead of the model's memory, the single chain was split into
separate steps: follow-up questions, search queries, and a summary. Search is limited to six
approved vet sites, and the summary must cite the pages it used. The form shrank to species and
concern, and the other three fields became fixed questions asked in the chat. Follow-ups became
one to three.

**The owner's words are recapped by code, not the model.** In real test chats, the model
sometimes changed what the owner had said when repeating it back. The recap is now built directly
from the owner's own words.

**Search had to cope with real-world failures.** One failed query used to throw away the good
results of the others. Each query now runs on its own. A search where every query fails is
retried after 1, 2 and 4 seconds, within 20 seconds in total, and if it still fails the summary is
written from general guidance with a notice that the search didn't work. The queries were also leaning towards illness pages, so at least one must now ask
whether the sign is normal or worrying.

**A browser page was added after all.** The plan ruled it out, but a reviewer can open a browser
page through a temporary link with nothing installed. The desktop window stayed for local work.

**MLflow was built later than planned, and differently.** It was pushed back during the chain
rewrite, until a review pointed out it is one of the brief's three requirements. It now saves to
a local database file instead of plain files, and records a trace of every model call with its
prompt, reply and timing. Real use then showed several ways tracking could break the chat, such
as a failed MLflow write turning a good reply into an error. Each was fixed, so tracking can never
change what the owner sees.

**The question limit moved fully into code.** At the limit, the backend still asked the model once
more and trusted it to stop. The model asked a fourth question anyway, and **Try again** repeated
the failure. Now the model isn't asked once the limit is reached.

**Emergencies got their own check on every message.** The follow-up chain had been the second
line of defence behind the phrase list, but it only saw the owner's words after the three fixed
questions, and it caught 2 of 7 clear emergencies. A separate chain now asks one yes-or-no
question on every message, and caught all 7 with no false alarms on ordinary statements.

**The default model changed from llama3 to gpt-oss:20b.** llama3 8B was fast for building and
testing. gpt-oss:20b gives more accurate answers, but needed changes to how structured replies are
requested, a lower reasoning setting so its thinking didn't use up the space for its answer, and a
larger context window: Ollama's small default was silently cutting the rules off long summary
prompts.

**The summary became stricter.** Pages about illnesses were pushing ordinary cases towards
"possible problem", so that outcome now needs something abnormal reported by the owner. Repeated
real chats also led to rejecting empty "nothing flagged" summaries, treating a repeated question as
"I have enough", and fixing phrase-list false alarms such as "wee" matching inside "week".

**Planned but not built yet:** the CI workflow, a full MLflow analysis command (a short example
script is in the [MLflow README](../src/mlflow_tracking/README.md#analyse-it)), and grading answers
with a second model. These are in the root README's [future work](../README.md#future-work).
