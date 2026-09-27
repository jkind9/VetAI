"""Regression tests for the owner-fact and balanced-retrieval boundaries."""

from __future__ import annotations

import pytest

from backend.model import SEARCH_PROMPT_PATH, SYNTHESIS_PROMPT_PATH, PromptFile
from backend.schemas import AdaptiveDecision, AssessmentDraft, TurnRequest
from backend.workflow import run_turn
from conftest import FakeChains, FakeSearcher, assessment_draft, intake, ready_history


def test_search_prompt_requires_a_normal_versus_concerning_query() -> None:
    rules = PromptFile.load(SEARCH_PROMPT_PATH).system.casefold()

    assert "at least one query" in rules
    assert "normal or expected" in rules
    assert "concerning or abnormal" in rules


def test_synthesis_prompt_requires_reported_abnormality_not_pathology_retrieval() -> None:
    rules = PromptFile.load(SYNTHESIS_PROMPT_PATH).system.casefold()

    assert "background references" in rules
    assert "positive abnormal fact reported by the owner" in rules
    assert "do not infer abnormality solely because retrieved pages describe" in rules


def test_synthesis_prompt_requires_useful_sections_for_nothing_flagged() -> None:
    rules = " ".join(PromptFile.load(SYNTHESIS_PROMPT_PATH).system.casefold().split())

    assert "at least one source-backed suggested action" in rules
    assert "at least one source-backed question for the veterinarian" in rules
    assert "including when `outcome` is `nothing_flagged`" in rules


def test_synthesis_prompt_requires_grounded_items_not_bare_strings() -> None:
    rules = " ".join(PromptFile.load(SYNTHESIS_PROMPT_PATH).system.casefold().split())

    assert '{{"text": "...", "source_ids": ["s1"]}}' in rules
    assert "never return a bare string" in rules
    assert "do not put citations inside `text`" in rules


def test_synthesis_prompt_allows_reasonable_general_knowledge_consistent_with_evidence() -> None:
    rules = " ".join(PromptFile.load(SYNTHESIS_PROMPT_PATH).system.casefold().split())

    assert "reasonable, widely accepted general veterinary guidance" in rules
    assert "must not contradict the evidence" in rules
    assert "never present general guidance as something the owner reported" in rules


def test_synthesis_prompt_handles_an_empty_evidence_list() -> None:
    rules = " ".join(PromptFile.load(SYNTHESIS_PROMPT_PATH).system.casefold().split())

    assert "if the evidence list is empty" in rules
    assert '`"source_ids": []`' in rules


def test_synthesis_schema_rejects_a_model_authored_owner_recap() -> None:
    raw_draft = assessment_draft().model_dump()
    raw_draft["what_you_reported"] = [
        "Your dog has brachycephalic obstructive airway syndrome."
    ]

    with pytest.raises(ValueError):
        AssessmentDraft.model_validate(raw_draft)


def test_assessment_recap_is_constructed_from_owner_words() -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[assessment_draft()],
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
