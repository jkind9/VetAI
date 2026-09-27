# Prompts

Each of the four model steps has its own prompt file. Keeping them apart means each prompt has one
job, and each can be changed and tested on its own.

| File | Model step | What the prompt tells the model |
| --- | --- | --- |
| `emergency_check.md` | Emergency check, on every message | Answer only yes or no: could the signs the owner reported need an emergency vet now? It lists the warning signs (from Cornell's emergency guidance), allows for pet names and misspellings, respects "she isn't having trouble breathing", and says to answer yes when unsure |
| `adaptive_question.md` | Follow-up question | Ask one short question for a detail not already given, or say there is enough. Never suggest a cause, treatment, or reassurance |
| `search_queries.md` | Search queries | Write one to three short, neutral queries. At least one must ask whether the main sign is normal or worrying. No personal details, web addresses or copied sentences |
| `evidence_synthesis.md` | Summary | Choose "possible problem" or "nothing flagged" and write the sections, citing the pages read. May add widely accepted general vet guidance that fits the report. If no pages were found, write from general guidance with no citations |

The model steps are told what they may not do, but the code enforces the rules that matter.
The code, not the prompts, decides:

- the three standard questions and when follow-ups start and stop;
- the emergency notice's wording, and that an emergency ends the chat;
- which websites search may use;
- that every citation is a page that was actually read;
- the recap of what the owner said, the outcome wording, and the disclaimer.

## File format

Each file has a `<!-- system -->` section (the instructions) and a `<!-- human -->` section (the
owner's details, filled in for each message). `PromptFile.load` in `src/backend/model.py` splits
the two and takes a SHA-256 fingerprint of the whole file. Every MLflow run records all four
fingerprints, so you can tell which prompt text produced which result.

## Changing a prompt

1. Edit the file, and bump the version in its title (for example "v1" to "v2").
2. Run `uv run pytest`. `tests/test_j3_regression.py` checks for rules that earlier real chats
   showed were needed, such as the normal-or-worrying search query.
3. Run the opt-in real-model checks (see [`tests/README.md`](../tests/README.md)), and compare
   runs before and after the change in MLflow using the prompt fingerprint.

Passing these checks shows the replies have the right shape. It doesn't show the advice is good:
that needs a person to review real chats against the rules in
[`documentation/test-cases.md`](../documentation/test-cases.md#human-review-rules).
