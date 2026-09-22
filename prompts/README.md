# Prompts

[`question_flow.md`](question_flow.md) is the whole prompt, version 1. The loader in
`src/backend/model.py` splits it at `<!-- system -->` and `<!-- human -->`, then builds a LangChain
`ChatPromptTemplate`. Curly-braced text is a template placeholder; literal braces need escaping.

The loader hashes the whole file, including these notes, and exposes it as
`model.prompt.sha256`. A future tracking layer can record that hash with a run, so any edit to the
prompt is visible in the record.

The prompt controls wording. The backend decides whether to call a model and whether this turn may
contain a question. It receives one of two mode instructions:

- **ordinary** — ask the single most useful follow-up question, or write the recap, whichever is
  more use.
- **summary_only** — two questions have already been asked; write the recap.

If the model asks a question in `summary_only`, `run_turn` rejects it; the cap does not depend on
prompt compliance.

The prompt is also told not to add a disclaimer. The application appends a fixed one to every
recap, so a model-written version would only duplicate it or water it down.

After editing, run `uv run pytest`. The fake-model tests do not read this prompt; also run the
optional real-model check in [the tests README](../tests/README.md) and review its output. Passing
tests do not establish question quality; use the human-review criteria in
[the test cases](../documentation/test-cases.md).
