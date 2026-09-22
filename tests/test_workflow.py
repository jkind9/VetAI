"""End-to-end policy tests for the deterministic and multi-chain stages."""

from __future__ import annotations

import pytest

from backend.questions import STANDARD_QUESTIONS
from backend.schemas import AdaptiveDecision, ModelOutputError, TurnRequest
import backend.workflow as workflow
from backend.workflow import ASSESSMENT_SUFFIX, EMERGENCY_NOTICE, run_turn
from conftest import (
    FakeChains,
    FakeSearcher,
    assessment_draft,
    history,
    intake,
    ready_history,
    standard_history,
)


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
    assert result.assessment.outcome == "possible_problem"
    assert result.assessment.outcome_wording == workflow.OUTCOME_WORDING["possible_problem"]
    assert result.assessment.suggested_actions[0].text.startswith("Record")
    assert [source.source_id for source in result.assessment.sources] == ["S1"]


@pytest.mark.parametrize("outcome", ["possible_problem", "nothing_flagged"])
def test_assessment_result_exposes_fixed_wording_for_each_supported_outcome(
    outcome: str,
) -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[assessment_draft(outcome=outcome)],
    )

    result = run_turn(
        TurnRequest(
            intake=intake(),
            history=ready_history(("Have you noticed discharge?", "No")),
        ),
        chains,
        FakeSearcher(),
    )

    assert result.assessment is not None
    assert result.assessment.outcome == outcome
    assert result.assessment.outcome_wording == workflow.OUTCOME_WORDING[outcome]


def test_after_three_adaptive_answers_makes_final_safety_call_then_searches_without_question() -> None:
    events: list[str] = []
    chains = FakeChains(adaptive=[{"kind": "ready_for_search"}], events=events)
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
    assert events == ["adaptive", "plan", "search", "synthesis"]
    assert chains.adaptive_calls[0][1] == "ready_or_escalate"


def test_after_three_adaptive_answers_final_safety_call_can_escalate() -> None:
    events: list[str] = []
    chains = FakeChains(adaptive=[{"kind": "urgent_escalation"}], events=events)
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

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert events == ["adaptive"]
    assert chains.adaptive_calls[0][1] == "ready_or_escalate"
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_ready_is_rejected_before_one_adaptive_answer() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])

    with pytest.raises(ModelOutputError) as raised:
        run_turn(TurnRequest(intake=intake(), history=standard_history()), chains, FakeSearcher())

    assert raised.value.reason == "question_required"


def test_adaptive_model_can_escalate_a_typo_not_seen_by_phrase_rules() -> None:
    events: list[str] = []
    chains = FakeChains(adaptive=[{"kind": "urgent_escalation"}], events=events)
    searcher = FakeSearcher(events=events)

    result = run_turn(
        TurnRequest(intake=intake("My dog is dieing"), history=standard_history()),
        chains,
        searcher,
    )

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert events == ["adaptive"]
    assert chains.plan_calls == []
    assert searcher.calls == []


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
