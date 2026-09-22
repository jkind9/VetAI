"""Emergency-first state machine for the bounded multi-chain conversation."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from backend.questions import STANDARD_QUESTIONS, next_standard_question
from backend.safeguards import find_emergency
from backend.schemas import (
    MAX_ADAPTIVE_QUESTIONS,
    STANDARD_QUESTION_COUNT,
    AdaptiveDecision,
    Assessment,
    AssessmentDraft,
    EvidenceItem,
    InvalidTurnRequest,
    Message,
    ModelOutputError,
    QuestionMode,
    Role,
    SearchPlan,
    SourceCitation,
    TurnRequest,
    TurnResult,
)

EMERGENCY_NOTICE = (
    "This may be an emergency. Please contact an emergency veterinarian now. "
    "This demo cannot assess your pet or provide a diagnosis."
)

ASSESSMENT_SUFFIX = (
    "This is not a diagnosis. Please discuss your pet's concern with a veterinarian."
)

TModel = TypeVar("TModel", bound=BaseModel)


def run_turn(turn: TurnRequest, chains: Any, searcher: Any) -> TurnResult:
    """Advance one safe state using deterministic policy around three model chains."""
    _validate_history(turn.history)

    emergency = find_emergency(_owner_written_text(turn))
    if emergency is not None:
        return TurnResult(
            kind="emergency_notice",
            reply=EMERGENCY_NOTICE,
            emergency_rule=emergency.rule,
        )

    completed_pairs = len(turn.history) // 2
    standard = next_standard_question(completed_pairs)
    if standard is not None:
        return TurnResult(
            kind="question",
            reply=standard.text,
            question_type="standard",
            question_id=standard.id,
        )

    adaptive_count = completed_pairs - STANDARD_QUESTION_COUNT
    if adaptive_count < MAX_ADAPTIVE_QUESTIONS:
        mode: QuestionMode = (
            "question_required" if adaptive_count == 0 else "question_or_ready"
        )
        raw_decision = _call_stage(
            "adaptive_question", chains.propose_adaptive_question, turn, mode
        )
        decision = _validate_chain_output(
            AdaptiveDecision, raw_decision, stage="adaptive_question"
        )
        if decision.kind == "question":
            return TurnResult(
                kind="question",
                reply=decision.question,
                question_type="adaptive",
            )
        if adaptive_count == 0:
            raise ModelOutputError("question_required", stage="adaptive_question")

    return _build_assessment(turn, chains, searcher)


def _validate_history(history: list[Message]) -> None:
    if len(history) % 2:
        raise InvalidTurnRequest(
            "chat history must end with the owner's answer to the last question"
        )
    for index, message in enumerate(history):
        expected: Role = "assistant" if index % 2 == 0 else "user"
        if message.role != expected:
            raise InvalidTurnRequest(
                f"chat history message {index} should be from the {expected}"
            )

    completed_pairs = len(history) // 2
    for pair_index in range(min(completed_pairs, STANDARD_QUESTION_COUNT)):
        actual = history[pair_index * 2].content
        expected = STANDARD_QUESTIONS[pair_index].text
        if actual != expected:
            raise InvalidTurnRequest(
                f"standard question {pair_index + 1} does not match the catalog"
            )


def _owner_written_text(turn: TurnRequest) -> list[str]:
    return [turn.intake.concern] + [
        message.content for message in turn.history if message.role == "user"
    ]


def _build_assessment(turn: TurnRequest, chains: Any, searcher: Any) -> TurnResult:
    raw_plan = _call_stage("search_query", chains.generate_search_plan, turn)
    plan = _validate_chain_output(SearchPlan, raw_plan, stage="search_query")

    try:
        evidence = searcher.search(plan)
    except ModelOutputError:
        raise
    except Exception as error:  # search implementations must not leak provider exceptions
        raise ModelOutputError(
            "search_failed", type(error).__name__, stage="approved_source_search"
        ) from error
    if not evidence:
        raise ModelOutputError(
            "insufficient_evidence", stage="approved_source_search"
        )

    raw_draft = _call_stage(
        "evidence_synthesis", chains.synthesise_assessment, turn, evidence
    )
    draft = _validate_chain_output(
        AssessmentDraft, raw_draft, stage="evidence_synthesis"
    )
    assessment = _ground_assessment(draft, evidence)
    return TurnResult(kind="assessment", assessment=assessment)


def _call_stage(stage: str, function: Any, *args: Any) -> Any:
    try:
        return function(*args)
    except ModelOutputError:
        raise
    except Exception as error:
        raise ModelOutputError(
            "model_call_failed", type(error).__name__, stage=stage
        ) from error


def _validate_chain_output(
    model: type[TModel], raw: Any, *, stage: str
) -> TModel:
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        raise ModelOutputError(
            "invalid_model_output",
            str(error.errors(include_url=False, include_input=False)),
            stage=stage,
        ) from error


def _ground_assessment(
    draft: AssessmentDraft, evidence: list[EvidenceItem]
) -> Assessment:
    evidence_by_id = {item.source_id: item for item in evidence}
    referenced_ids: set[str] = set()
    for collection in (
        draft.possible_areas,
        draft.useful_observations,
        draft.questions_for_veterinarian,
    ):
        for grounded in collection:
            referenced_ids.update(grounded.source_ids)

    unknown = referenced_ids.difference(evidence_by_id)
    if unknown:
        raise ModelOutputError(
            "ungrounded_synthesis",
            f"unknown source IDs: {sorted(unknown)}",
            stage="evidence_synthesis",
        )

    sources = [
        SourceCitation(
            source_id=item.source_id,
            title=item.title,
            url=item.url,
            organisation=item.organisation,
        )
        for item in evidence
        if item.source_id in referenced_ids
    ]
    return Assessment(
        what_you_reported=draft.what_you_reported,
        possible_areas=draft.possible_areas,
        useful_observations=draft.useful_observations,
        questions_for_veterinarian=draft.questions_for_veterinarian,
        sources=sources,
        disclaimer=ASSESSMENT_SUFFIX,
    )
