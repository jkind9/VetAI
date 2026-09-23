"""Opt-in structured-output checks for each real local LangChain stage."""

from __future__ import annotations

import os

import pytest

from backend.schemas import EvidenceItem, TurnRequest
from conftest import evidence, intake, ready_history, standard_history

pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(
        os.environ.get("VETAI_RUN_OLLAMA_SMOKE") != "1",
        reason="set VETAI_RUN_OLLAMA_SMOKE=1 and start Ollama",
    ),
]

MODEL_TAG = os.environ.get("VETAI_OLLAMA_MODEL", "llama3:latest")


@pytest.fixture(scope="module")
def chains():
    from backend.model import OllamaChatModel

    return OllamaChatModel(MODEL_TAG)


def test_adaptive_chain_returns_a_required_question(chains) -> None:
    result = chains.propose_adaptive_question(
        TurnRequest(intake=intake(), history=standard_history()),
        "question_required",
    )

    assert result.kind == "question"
    assert result.question


def test_adaptive_chain_can_escalate_urgent_misspelled_context(chains) -> None:
    result = chains.propose_adaptive_question(
        TurnRequest(
            intake=intake("My dog looks like she is dieing and is barely responsive."),
            history=standard_history(),
        ),
        "question_required",
    )

    assert result.kind == "urgent_escalation"
    assert result.question is None


def test_query_and_synthesis_chains_return_structured_outputs(chains) -> None:
    turn = TurnRequest(
        intake=intake(), history=ready_history(("Any discharge?", "No"))
    )
    plan = chains.generate_search_plan(turn)
    result = chains.synthesise_assessment(turn, [evidence()])

    assert plan.queries
    assert result.outcome in {"possible_problem", "nothing_flagged"}
    assert all(item.source_ids for item in result.possible_areas)
    assert all(item.source_ids for item in result.suggested_actions)


def test_evidence_shape_for_real_synthesis_is_valid() -> None:
    assert EvidenceItem.model_validate(evidence().model_dump()).source_id == "S1"
