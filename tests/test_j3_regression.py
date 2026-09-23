"""Regression tests for the owner-fact and balanced-retrieval boundaries."""

from __future__ import annotations

from backend.model import PromptFile, SEARCH_PROMPT_PATH
from backend.schemas import AdaptiveDecision, TurnRequest
from backend.workflow import run_turn
from conftest import FakeChains, FakeSearcher, assessment_draft, intake, ready_history


def test_search_prompt_requires_a_normal_versus_concerning_query() -> None:
    rules = PromptFile.load(SEARCH_PROMPT_PATH).system.casefold()

    assert "at least one query" in rules
    assert "normal or expected" in rules
    assert "concerning or abnormal" in rules


def test_assessment_recap_uses_owner_words_not_synthesis_output() -> None:
    hallucinated_draft = assessment_draft().model_copy(
        update={
            "what_you_reported": [
                "Your dog has brachycephalic obstructive airway syndrome."
            ]
        }
    )
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[hallucinated_draft],
    )
    request = TurnRequest(
        intake=intake("My dog has been panting more than usual while resting."),
        history=ready_history(
            (
                "Is she otherwise behaving normally?",
                "She settles while asleep, is eating and drinking, and has no vomiting.",
            )
        ),
    )

    result = run_turn(request, chains, FakeSearcher())

    assert result.assessment is not None
    assert result.assessment.what_you_reported == [
        "Concern: My dog has been panting more than usual while resting.",
        "Duration: Since this morning",
        "Previous occurrence: No",
        "Pattern: It comes and goes",
        (
            "Additional detail 1: She settles while asleep, is eating and drinking, "
            "and has no vomiting."
        ),
    ]

