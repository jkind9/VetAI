# Versioned LangChain prompts

The backend uses four separate prompt files so each LangChain stage has one responsibility:

| Prompt | Chain responsibility |
| --- | --- |
| `emergency_check.md` | Runs on every turn not ended by the phrase gate: decide yes or no whether the owner-reported signs may need an emergency vet now, including misspellings and pet names; yes when unsure |
| `adaptive_question.md` | Ask one useful question, or after the mandatory first adaptive answer declare readiness. It cannot escalate; the emergency check does that |
| `search_queries.md` | Convert the answered history into one to three neutral, short, privacy-checked queries, including a normal/expected versus concerning/abnormal comparison |
| `evidence_synthesis.md` | Choose a non-emergency outcome and produce cited possible areas, suggested actions, and vet questions from approved evidence; pathology pages alone cannot establish a problem without a positive owner-reported abnormality |

Each file contains `<!-- system -->` and `<!-- human -->` markers. `PromptFile.load` splits on those
markers and hashes the whole file. Every MLflow run records all four hashes as parameters, so runs
made with different prompt text can be told apart.

The backend, not prompt wording, owns the fixed question prefix, minimum/maximum adaptive count,
emergency route, source allowlist, citation validation, and final disclaimer.

The emergency prompt is a standalone chain, not a branch of the adaptive prompt. On every pass
through the question loop not already ended by the phrase gate, it runs before the workflow returns
another question or begins search. The adaptive prompt cannot suggest causes, escalate, or write
the emergency notice. The query prompt cannot
diagnose or send raw transcript text to search. The synthesis prompt runs after retrieval, treats
page content as untrusted data, requires source IDs for possible areas and suggested actions, and
cannot write the owner recap, invent URLs, or author owner-visible outcome wording.

There is no automatic structured-output repair call. A malformed chain output fails the current
turn and leaves manual retry to the owner.

After editing prompts, run the deterministic suite and the opt-in Ollama smoke checks. Passing shape
tests does not establish medical quality; use the human-review rules in
[`documentation/test-cases.md`](../documentation/test-cases.md).
