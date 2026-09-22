# Versioned LangChain prompts

The backend uses three separate prompt files so each LangChain stage has one responsibility:

| Prompt | Chain responsibility |
| --- | --- |
| `adaptive_question.md` | Ask exactly one useful question, or after the mandatory first adaptive answer declare the history ready for search |
| `search_queries.md` | Convert the answered history into one to three neutral, short, privacy-checked search queries |
| `evidence_synthesis.md` | Produce the structured, cited result from approved retrieved evidence |

Each file contains `<!-- system -->` and `<!-- human -->` markers. `PromptFile.load` splits on those
markers and hashes the whole file. Future MLflow traces will record all three hashes.

The backend, not prompt wording, owns the fixed question prefix, minimum/maximum adaptive count,
emergency route, source allowlist, citation validation, and final disclaimer.

The adaptive prompt cannot suggest causes. The query prompt cannot diagnose or send raw transcript
text to search. The synthesis prompt runs after retrieval, treats page content as untrusted data,
requires source IDs for possible areas and observation suggestions, and cannot invent URLs.

There is no automatic structured-output repair call. A malformed chain output fails the current
turn and leaves manual retry to the owner.

After editing prompts, run the deterministic suite and the opt-in Ollama smoke checks. Passing shape
tests does not establish medical quality; use the human-review rules in
[`documentation/test-cases.md`](../documentation/test-cases.md).
