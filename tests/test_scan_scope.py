"""Which text the safety gate reads — the half of the rule the phrase tests cannot see.

`test_safeguards.py` checks that a phrase matches a string. These check that `run_turn` hands
the gate the owner's words and only the owner's words. Two wrong implementations pass every
other test in the suite and fail here:

- scanning only the concern breaks E5 and E8, so a warning sign reported in a follow-up answer
  or in the duration field gets a model-written question instead of the notice;
- scanning every message regardless of who wrote it breaks O8, so the demo escalates on its own
  question rather than on anything the owner said.
"""

from __future__ import annotations

from backend.schemas import TurnRequest
from backend.workflow import EMERGENCY_NOTICE, run_turn
from conftest import FakeChatModel, history, intake, question, summary


def test_a_warning_sign_in_a_later_answer_is_caught() -> None:
    """E5: the owner escalates on turn two; the model is not called again."""
    model = FakeChatModel(question())
    request = TurnRequest(
        intake=intake("My dog seems quieter than usual."),
        history=history(("Has anything else changed?", "Now she is struggling to breathe.")),
    )

    result = run_turn(request, model)

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert model.calls == []


def test_the_duration_field_is_scanned_too() -> None:
    """E8: an ordinary concern, but the owner typed a warning sign into the duration box."""
    model = FakeChatModel(question())
    request = TurnRequest(
        intake=intake(
            "My dog is scratching one ear.", duration="Since she collapsed this morning."
        ),
        history=[],
    )

    result = run_turn(request, model)

    assert result.kind == "emergency_notice"
    assert model.calls == []


def test_the_assistants_own_question_is_never_scanned() -> None:
    """O8: asking "Is she struggling to breathe?" must not escalate when the answer is "No."."""
    model = FakeChatModel(summary("You reported that your dog scratched one ear."))
    request = TurnRequest(
        intake=intake("My dog scratched one ear."),
        history=history(("Is she struggling to breathe?", "No.")),
    )

    result = run_turn(request, model)

    assert result.kind == "summary", "the assistant's wording is not an owner report"
    assert len(model.calls) == 1


def test_the_emergency_rule_is_named_on_the_result() -> None:
    """Which rule fired is carried out of the workflow, so tracking can record it later."""
    model = FakeChatModel(question())
    request = TurnRequest(intake=intake("My dog may have swallowed a medication."), history=[])

    result = run_turn(request, model)

    assert result.emergency_rule == "suspected_ingestion"
