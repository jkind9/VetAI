"""Invalid chain shapes, history boundaries, and citation grounding never reach the owner."""

from __future__ import annotations

import pytest

from backend.schemas import (
    AdaptiveDecision,
    AssessmentDraft,
    Message,
    ModelOutputError,
    SearchPlan,
    TurnRequest,
)
from backend.workflow import run_turn
from conftest import FakeChains, FakeSearcher, assessment_draft, intake, ready_history


def test_urgent_escalation_decision_has_no_question() -> None:
    decision = AdaptiveDecision(kind="urgent_escalation")

    assert decision.kind == "urgent_escalation"
    assert decision.question is None


@pytest.mark.parametrize("raw", [None, "question", {}, {"kind": "question"}])
def test_invalid_adaptive_output_is_a_parse_failure(raw: object) -> None:
    chains = FakeChains(adaptive=[raw])

    with pytest.raises(ModelOutputError) as raised:
        run_turn(TurnRequest(intake=intake(), history=ready_history()), chains, FakeSearcher())

    assert raised.value.reason == "invalid_model_output"
    assert raised.value.stage == "adaptive_question"


@pytest.mark.parametrize("raw", [None, {}, {"queries": []}, {"queries": ["x" * 121]}])
def test_invalid_search_plan_stops_before_search(raw: object) -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        plans=[raw],
    )
    searcher = FakeSearcher()

    with pytest.raises(ModelOutputError) as raised:
        run_turn(
            TurnRequest(
                intake=intake(),
                history=ready_history(("Any other changes?", "No")),
            ),
            chains,
            searcher,
        )

    assert raised.value.reason == "invalid_model_output"
    assert raised.value.stage == "search_query"
    assert searcher.calls == []


def test_unknown_synthesis_source_id_is_rejected() -> None:
    bad = assessment_draft(source_id="S99")
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        plans=[SearchPlan(queries=["dog ear scratching veterinary"])],
        assessments=[bad],
    )

    with pytest.raises(ModelOutputError) as raised:
        run_turn(
            TurnRequest(
                intake=intake(),
                history=ready_history(("Any other changes?", "No")),
            ),
            chains,
            FakeSearcher(),
        )

    assert raised.value.reason == "ungrounded_synthesis"
    assert raised.value.stage == "evidence_synthesis"


def test_synthesis_requires_citations_for_each_grounded_item() -> None:
    with pytest.raises(ValueError):
        AssessmentDraft.model_validate(
            {
                "outcome": "possible_problem",
                "possible_areas": [{"text": "An area", "source_ids": []}],
                "suggested_actions": [],
                "questions_for_veterinarian": [],
            }
        )


def test_assessment_draft_requires_a_supported_outcome_and_application_owns_wording() -> None:
    draft = assessment_draft()

    assert draft.outcome in {"possible_problem", "nothing_flagged"}
    assert draft.suggested_actions[0].text.startswith("Record")

    with pytest.raises(ValueError):
        AssessmentDraft.model_validate(
            {
                "outcome": "urgent_escalation",
                "possible_areas": [{"text": "An area", "source_ids": ["S1"]}],
                "suggested_actions": [
                    {"text": "Record the episode for the vet.", "source_ids": ["S1"]}
                ],
                "questions_for_veterinarian": [
                    {"text": "What should I mention?", "source_ids": ["S1"]}
                ],
            }
        )

    with pytest.raises(ValueError):
        AssessmentDraft.model_validate(
            {
                "outcome": "possible_problem",
                "outcome_wording": "The model supplied this wording.",
                "possible_areas": [{"text": "An area", "source_ids": ["S1"]}],
                "suggested_actions": [
                    {"text": "Record the episode for the vet.", "source_ids": ["S1"]}
                ],
                "questions_for_veterinarian": [
                    {"text": "What should I mention?", "source_ids": ["S1"]}
                ],
            }
        )


@pytest.mark.parametrize(
    ("outcome", "possible_areas"),
    [
        ("possible_problem", []),
        ("nothing_flagged", [{"text": "An area", "source_ids": ["S1"]}]),
    ],
)
def test_assessment_outcome_matches_possible_areas(
    outcome: str, possible_areas: list[dict[str, object]]
) -> None:
    with pytest.raises(ValueError):
        AssessmentDraft.model_validate(
            {
                "outcome": outcome,
                "possible_areas": possible_areas,
                "suggested_actions": [
                    {"text": "Record the episode for the vet.", "source_ids": ["S1"]}
                ],
                "questions_for_veterinarian": [
                    {"text": "What should I mention?", "source_ids": ["S1"]}
                ],
            }
        )


def test_history_rejects_more_than_six_complete_pairs() -> None:
    messages: list[Message] = []
    for index in range(7):
        messages.extend(
            [
                Message(role="assistant", content=f"Question {index}?"),
                Message(role="user", content=f"Answer {index}"),
            ]
        )

    with pytest.raises(ValueError):
        TurnRequest(intake=intake(), history=messages)
