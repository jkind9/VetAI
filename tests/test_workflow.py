"""End-to-end policy tests for the deterministic and multi-chain stages."""

from __future__ import annotations

import pytest

import backend.workflow as workflow
from backend.questions import STANDARD_QUESTIONS
from backend.schemas import AdaptiveDecision, ModelOutputError, TurnRequest
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
def test_the_model_check_runs_before_each_fixed_question(completed: int) -> None:
    events: list[str] = []
    chains = FakeChains(events=events)
    searcher = FakeSearcher()
    answers = ["Today", "No", "It comes and goes"]
    pairs = [(STANDARD_QUESTIONS[i].text, answers[i]) for i in range(completed)]

    result = run_turn(TurnRequest(intake=intake(), history=history(*pairs)), chains, searcher)

    expected = STANDARD_QUESTIONS[completed]
    assert result.kind == "question"
    assert result.reply == expected.text
    assert result.question_type == "standard"
    assert result.question_id == expected.id
    assert events == ["emergency_check"]
    assert chains.emergency_calls == [
        TurnRequest(intake=intake(), history=history(*pairs))
    ]
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


def test_the_model_check_runs_on_the_first_turn() -> None:
    events: list[str] = []
    chains = FakeChains(emergency=[{"emergency": True}], events=events)
    searcher = FakeSearcher(events=events)

    result = run_turn(
        TurnRequest(intake=intake("My dog is dieing"), history=[]), chains, searcher
    )

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert result.emergency_rule == "model_emergency_check"
    assert events == ["emergency_check"]
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
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

    assert events == ["emergency_check", "adaptive", "plan", "search", "synthesis"]
    assert chains.adaptive_calls[0][1] == "question_or_ready"
    assert result.kind == "assessment"
    assert result.assessment is not None
    assert result.assessment.disclaimer == ASSESSMENT_SUFFIX
    assert result.assessment.outcome == "possible_problem"
    assert result.assessment.outcome_wording == workflow.OUTCOME_WORDING["possible_problem"]
    assert result.assessment.suggested_actions[0].text.startswith("Record")
    assert [source.source_id for source in result.assessment.sources] == ["S1"]


def test_repeated_adaptive_question_moves_to_search_after_one_answer() -> None:
    events: list[str] = []
    repeated_question = "What is your dog's age?"
    chains = FakeChains(
        adaptive=[
            AdaptiveDecision(kind="question", question=repeated_question)
        ],
        events=events,
    )
    searcher = FakeSearcher(events=events)
    request = TurnRequest(
        intake=intake(),
        history=ready_history((repeated_question, "Five years old")),
    )

    result = run_turn(request, chains, searcher)

    assert result.kind == "assessment"
    assert events == ["emergency_check", "adaptive", "plan", "search", "synthesis"]


def test_rephrased_age_question_moves_to_search_after_one_answer() -> None:
    events: list[str] = []
    chains = FakeChains(
        adaptive=[
            AdaptiveDecision(kind="question", question="How old is your dog?")
        ],
        events=events,
    )
    searcher = FakeSearcher(events=events)
    request = TurnRequest(
        intake=intake(),
        history=ready_history(("What is your dog's age?", "Five years old")),
    )

    result = run_turn(request, chains, searcher)

    assert result.kind == "assessment"
    assert events == ["emergency_check", "adaptive", "plan", "search", "synthesis"]


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


THREE_ADAPTIVE_PAIRS = (
    ("Question one?", "Answer one"),
    ("Question two?", "Answer two"),
    ("Question three?", "Answer three"),
)


def test_after_three_adaptive_answers_the_model_is_not_asked_again() -> None:
    # The code counts the follow-up questions, so a fourth one cannot be asked for.
    events: list[str] = []
    chains = FakeChains(adaptive=[], events=events)
    searcher = FakeSearcher(events=events)
    request = TurnRequest(intake=intake(), history=ready_history(*THREE_ADAPTIVE_PAIRS))

    result = run_turn(request, chains, searcher)

    assert result.kind == "assessment"
    assert events == ["emergency_check", "plan", "search", "synthesis"]
    assert chains.adaptive_calls == []


def test_the_last_answer_is_checked_before_search() -> None:
    events: list[str] = []
    chains = FakeChains(
        emergency=[{"emergency": True}], adaptive=[], events=events
    )
    searcher = FakeSearcher(events=events)
    request = TurnRequest(intake=intake(), history=ready_history(*THREE_ADAPTIVE_PAIRS))

    result = run_turn(request, chains, searcher)

    assert result.kind == "emergency_notice"
    assert result.emergency_rule == "model_emergency_check"
    assert events == ["emergency_check"]
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_an_emergency_phrase_in_the_third_answer_still_stops_the_chat() -> None:
    chains = FakeChains(adaptive=[])
    searcher = FakeSearcher()
    pairs = (*THREE_ADAPTIVE_PAIRS[:2], ("Question three?", "She collapsed a minute ago"))
    request = TurnRequest(intake=intake(), history=ready_history(*pairs))

    result = run_turn(request, chains, searcher)

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_ready_is_rejected_before_one_adaptive_answer() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])

    with pytest.raises(ModelOutputError) as raised:
        run_turn(TurnRequest(intake=intake(), history=standard_history()), chains, FakeSearcher())

    assert raised.value.reason == "question_required"


def test_the_dedicated_model_check_can_escalate_a_typo_not_seen_by_phrase_rules() -> None:
    events: list[str] = []
    chains = FakeChains(emergency=[{"emergency": True}], events=events)
    searcher = FakeSearcher(events=events)

    result = run_turn(
        TurnRequest(intake=intake("My dog is dieing"), history=[]),
        chains,
        searcher,
    )

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert result.emergency_rule == "model_emergency_check"
    assert events == ["emergency_check"]
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []
    assert searcher.calls == []


def test_a_failed_check_stops_the_turn() -> None:
    failure = ModelOutputError("timeout", stage="emergency_check")
    chains = FakeChains(emergency=[failure])

    with pytest.raises(ModelOutputError) as raised:
        run_turn(TurnRequest(intake=intake(), history=[]), chains, FakeSearcher())

    assert raised.value is failure
    assert raised.value.stage == "emergency_check"
    assert chains.adaptive_calls == []
    assert chains.plan_calls == []


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
    assert chains.emergency_calls == []
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
    assert chains.emergency_calls == []
    assert chains.adaptive_calls == []
    assert searcher.calls == []


def _uncited_draft() -> dict:
    raw = assessment_draft().model_dump()
    for section in ("possible_areas", "suggested_actions", "questions_for_veterinarian"):
        for item in raw[section]:
            item["source_ids"] = []
    return raw


@pytest.mark.parametrize(
    "search_error",
    [
        ModelOutputError("search_failed", stage="approved_source_search"),
        ModelOutputError("no_search_results", stage="approved_source_search"),
        ModelOutputError("insufficient_evidence", stage="approved_source_search"),
        TimeoutError("provider timed out"),
    ],
)
def test_search_failure_still_returns_an_assessment_with_a_notice(
    search_error: Exception,
) -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[_uncited_draft()],
    )
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    result = run_turn(request, chains, FakeSearcher(error=search_error))

    assert result.kind == "assessment"
    assert result.assessment is not None
    assert result.assessment.search_notice == workflow.SEARCH_UNAVAILABLE_NOTICE
    assert result.assessment.sources == []
    assert chains.synthesis_calls[0][1] == []


def test_empty_search_results_list_is_treated_as_a_failed_search() -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[_uncited_draft()],
    )
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    result = run_turn(request, chains, FakeSearcher(results=[]))

    assert result.assessment is not None
    assert result.assessment.search_notice == workflow.SEARCH_UNAVAILABLE_NOTICE


def test_successful_search_has_no_notice() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    result = run_turn(request, chains, FakeSearcher())

    assert result.assessment is not None
    assert result.assessment.search_notice is None


def test_unsafe_search_query_still_fails_the_turn() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher(
        error=ModelOutputError("unsafe_search_query", stage="approved_source_search")
    )
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    with pytest.raises(ModelOutputError) as raised:
        run_turn(request, chains, searcher)

    assert raised.value.reason == "unsafe_search_query"
    assert chains.synthesis_calls == []


def test_uncited_item_is_rejected_when_sources_were_found() -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[_uncited_draft()],
    )
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    with pytest.raises(ModelOutputError) as raised:
        run_turn(request, chains, FakeSearcher())

    assert raised.value.reason == "ungrounded_synthesis"


def test_cited_item_is_rejected_when_search_failed() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher(
        error=ModelOutputError("search_failed", stage="approved_source_search")
    )
    request = TurnRequest(intake=intake(), history=ready_history(("Any discharge?", "No")))

    with pytest.raises(ModelOutputError) as raised:
        run_turn(request, chains, searcher)

    assert raised.value.reason == "ungrounded_synthesis"
