"""The three behaviours the rest of the system is built around.

Each maps to a case in documentation/test-cases.md: E1 (emergency bypass), O6 (a second
follow-up is allowed), O5 and C3 (after two follow-ups only a recap is accepted).

These assert on control flow, not on model prose: which route was taken, how many model calls
happened, and what mode the workflow asked for.
"""

from __future__ import annotations

import pytest

from backend.schemas import ModelOutputError, TurnRequest
from backend.workflow import EMERGENCY_NOTICE, SUMMARY_SUFFIX, run_turn
from conftest import FakeChatModel, history, intake, question, summary


def test_emergency_phrase_bypasses_the_model() -> None:
    """E1: a curated warning phrase returns the fixed notice without consulting the model."""
    model = FakeChatModel(question())
    request = TurnRequest(intake=intake("My dog is struggling to breathe."), history=[])

    result = run_turn(request, model)

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert model.calls == [], "the model must not be asked once a warning phrase matched"


def test_one_prior_question_permits_a_second() -> None:
    """O6: with one question already asked, the model may still ask another."""
    model = FakeChatModel(question("Has it been constant since yesterday, or on and off?"))
    request = TurnRequest(
        intake=intake(),
        history=history(("When did you notice it?", "Yesterday")),
    )

    result = run_turn(request, model)

    assert result.kind == "question"
    assert len(model.calls) == 1
    assert model.modes[0] == "ordinary", "one prior question must not force a recap"


def test_two_prior_questions_require_a_summary() -> None:
    """O5: after two questions the workflow asks for a recap only, and appends the suffix."""
    model = FakeChatModel(summary("You reported an ear concern that started yesterday."))
    request = TurnRequest(
        intake=intake(),
        history=history(
            ("When did you notice it?", "Yesterday"),
            ("Is it constant?", "On and off"),
        ),
    )

    result = run_turn(request, model)

    assert result.kind == "summary"
    assert len(model.calls) == 1
    assert model.modes[0] == "summary_only"
    assert result.reply.endswith(SUMMARY_SUFFIX)


def test_a_third_question_is_refused_even_if_the_model_returns_one() -> None:
    """C3: the cap is enforced by the workflow, not by the model's cooperation."""
    model = FakeChatModel(question("And has she eaten today?"))
    request = TurnRequest(
        intake=intake(),
        history=history(
            ("When did you notice it?", "Yesterday"),
            ("Is it constant?", "On and off"),
        ),
    )

    with pytest.raises(ModelOutputError) as raised:
        run_turn(request, model)

    assert raised.value.reason == "question_limit_violation"
    assert raised.value.parse_failure is False
    assert len(model.calls) == 1, "no retry: one model call per turn"
