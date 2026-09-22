# Tests

Run them with `uv run pytest`. No model, no network, no display — the stand-in model in
[`conftest.py`](conftest.py) returns one fixed answer and records every call as a
turn in `calls` and each mode in `modes`, so a test can assert both whether the model was asked
at all and which mode the workflow asked for.

| File | What it pins |
| --- | --- |
| `test_workflow.py` | The four routing decisions: the emergency bypass (E1), a second follow-up being allowed (O6), a recap after two (O5), and a third question being refused even when the model returns one (C3). |
| `test_scan_scope.py` | *Which* text the safety gate reads: a later owner answer (E5), the duration box (E8), and never the assistant's own question (O8). |
| `test_safeguards.py` | The phrase rules themselves: four positive categories, capitals and punctuation, the negated phrase (O3), near misses (O9), and hedged ingestion that must still match (E6). |
| `test_model_output.py` | Structural model-output failures, malformed history (C4, C6), and the fixed suffix being appended once. |
| `test_ollama_smoke.py` | One real local model, skipped by default. |

Case IDs refer to [the behavioural test cases](../documentation/test-cases.md).

`test_safeguards.py` hands strings straight to the matcher, so it cannot see which fields the
workflow passes in. `test_scan_scope.py` catches scanning only the concern (E5/E8) or scanning
assistant messages too (O8).

Model-output validation checks structure only: an allowed `kind` and a non-blank reply within the
length limit. A mapping and a `ModelReply` both pass; a plain string, `None`, or a structured
object of some other shape is a parse failure. It does not assess whether a reply is relevant,
factual, or medically appropriate. The follow-up cap is a separate check in `run_turn`.

```bash
VETAI_RUN_OLLAMA_SMOKE=1 uv run pytest tests/test_ollama_smoke.py -v -s
```

Needs Ollama running and the model pulled. Override the tag with `VETAI_OLLAMA_MODEL`. Each case
runs the real model through `run_turn`, and asserts the result kind, the `summary_only` routing and
suffix, and the emergency bypass. Model wording is reviewed by a person against the criteria in the
test-cases document, not asserted word for word.

Still to come: the HTTP layer's status codes, the MLflow run contents, the desktop client's error
mapping, and the opt-in fixed-case evaluation described in the
[plan](../documentation/implementation-plan.md).
