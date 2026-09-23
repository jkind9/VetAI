# Versioned LangChain prompts

The backend uses three separate prompt files so each LangChain stage has one responsibility:

| Prompt | Chain responsibility |
| --- | --- |
| `adaptive_question.md` | Escalate urgent context (including misspellings), ask one useful question, or after the mandatory first adaptive answer declare readiness |
| `search_queries.md` | Convert the answered history into one to three neutral, short, privacy-checked queries, including a normal/expected versus concerning/abnormal comparison |
| `evidence_synthesis.md` | Choose a non-emergency outcome and produce cited possible areas, suggested actions, and vet questions from approved evidence |

Each file contains `<!-- system -->` and `<!-- human -->` markers. `PromptFile.load` splits on those
markers and hashes the whole file. Every MLflow run records all three hashes as parameters, so runs
made with different prompt text can be told apart.

The backend, not prompt wording, owns the fixed question prefix, minimum/maximum adaptive count,
emergency route, source allowlist, citation validation, and final disclaimer.

The adaptive prompt cannot suggest causes or write the emergency notice. The query prompt cannot
diagnose or send raw transcript text to search. The synthesis prompt runs after retrieval, treats
page content as untrusted data, requires source IDs for possible areas and suggested actions, and
cannot write the owner recap, invent URLs, or author owner-visible outcome wording.

There is no automatic structured-output repair call. A malformed chain output fails the current
turn and leaves manual retry to the owner.

After editing prompts, run the deterministic suite and the opt-in Ollama smoke checks. Passing shape
tests does not establish medical quality; use the human-review rules in
[`documentation/test-cases.md`](../documentation/test-cases.md).
