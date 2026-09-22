"""End-to-end policy tests for the deterministic and multi-chain stages."""

from __future__ import annotations

import pytest

from backend.questions import STANDARD_QUESTIONS
from backend.schemas import AdaptiveDecision, ModelOutputError, TurnRequest
from backend.workflow import ASSESSMENT_SUFFIX, EMERGENCY_NOTICE, run_turn
from conftest import FakeChains, FakeSearcher, history, intake, ready_history, standard_history


@pytest.mark.parametrize("completed", [0, 1, 2])
def test_three_standard_questions_are_returned_without_model_or_search(completed: int) -> None:
    chains = FakeChains()
    searcher = FakeSearcher()
    answers = ["Today", "No", "It comes and goes"]
    pairs = [(STANDARD_QUESTIONS[i].text, answers[i]) for i in range(completed)]

    result = run_turn(TurnRequest(intake=intake(), history=history(*pairs)), chains, searcher)

    expected = STANDARD_QUESTIONS[completed]
    assert result.kind == "question"
    assert result.reply == expected.text
    assert result.question_type == "standard"
    assert result.question_id == expected.id
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_the_first_adaptive_question_is_mandatory() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="question", question="Any discharge?")])
    searcher = FakeSearcher()

    result = run_turn(
        TurnRequest(intake=intake(), history=standard_history()), chains, searcher
    )

    assert result.kind == "question"
    assert result.question_type == "adaptive"
    assert result.reply == "Any discharge?"
    assert chains.adaptive_calls[0][1] == "question_required"
    assert searcher.calls == []


def test_ready_after_one_adaptive_answer_runs_plan_search_then_synthesis() -> None:
    events: list[str] = []
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")], events=events
    )
    searcher = FakeSearcher(events=events)
    request = TurnRequest(
        intake=intake(),
        history=ready_history(("Have you noticed discharge?", "No")),
    )

    result = run_turn(request, chains, searcher)

    assert events == ["adaptive", "plan", "search", "synthesis"]
    assert chains.adaptive_calls[0][1] == "question_or_ready"
    assert result.kind == "assessment"
    assert result.assessment is not None
    assert result.assessment.disclaimer == ASSESSMENT_SUFFIX
    assert [source.source_id for source in result.assessment.sources] == ["S1"]


def test_after_three_adaptive_answers_search_is_forced_without_another_question_call() -> None:
    events: list[str] = []
    chains = FakeChains(adaptive=[], events=events)
    searcher = FakeSearcher(events=events)
    request = TurnRequest(
        intake=intake(),
        history=ready_history(
            ("Question one?", "Answer one"),
            ("Question two?", "Answer two"),
            ("Question three?", "Answer three"),
        ),
    )

    result = run_turn(request, chains, searcher)

    assert result.kind == "assessment"
    assert events == ["plan", "search", "synthesis"]
    assert chains.adaptive_calls == []


def test_ready_is_rejected_before_one_adaptive_answer() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])

    with pytest.raises(ModelOutputError) as raised:
        run_turn(TurnRequest(intake=intake(), history=standard_history()), chains, FakeSearcher())

    assert raised.value.reason == "question_required"


def test_warning_in_any_owner_answer_bypasses_every_chain_and_search() -> None:
    chains = FakeChains()
    searcher = FakeSearcher()
    request = TurnRequest(
        intake=intake("My dog seems quieter."),
        history=history((STANDARD_QUESTIONS[0].text, "Now she is struggling to breathe.")),
    )

    result = run_turn(request, chains, searcher)

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_initial_emergency_still_bypasses_every_stage() -> None:
    chains = FakeChains()
    searcher = FakeSearcher()

    result = run_turn(
        TurnRequest(intake=intake("My dog may have swallowed a medication."), history=[]),
        chains,
        searcher,
    )

    assert result.kind == "emergency_notice"
    assert result.emergency_rule == "suspected_ingestion"
    assert chains.adaptive_calls == []
    assert searcher.calls == []
