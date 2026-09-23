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

OUTCOME_WORDING = {
    "possible_problem": (
        "The information reviewed raised points to discuss with a veterinarian."
    ),
    "nothing_flagged": (
        "This review did not flag a specific problem. This is not an all-clear; keep monitoring "
        "your pet and contact a veterinarian if you remain concerned or the signs change."
    ),
}

STANDARD_REPORT_LABELS = ("Duration", "Previous occurrence", "Pattern")

TModel = TypeVar("TModel", bound=BaseModel)


def run_turn(turn: TurnRequest, chains: Any, searcher: Any) -> TurnResult:
    """Advance one safe state using deterministic policy around three model chains."""
    _validate_history(turn.history)

    emergency = find_emergency(_owner_written_text(turn))
    if emergency is not None:
        return _emergency_result(emergency.rule)

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
    mode: QuestionMode
    if adaptive_count == 0:
        mode = "question_required"
    elif adaptive_count < MAX_ADAPTIVE_QUESTIONS:
        mode = "question_or_ready"
    else:
        mode = "ready_or_escalate"

    raw_decision = _call_stage(
        "adaptive_question", chains.propose_adaptive_question, turn, mode
    )
    decision = _validate_chain_output(
        AdaptiveDecision, raw_decision, stage="adaptive_question"
    )
    if decision.kind == "urgent_escalation":
        return _emergency_result("model_urgent_escalation")
    if decision.kind == "question":
        if mode == "ready_or_escalate":
            raise ModelOutputError(
                "invalid_model_output",
                "adaptive question cap has been reached",
                stage="adaptive_question",
            )
        return TurnResult(
            kind="question",
            reply=decision.question,
            question_type="adaptive",
        )
    if adaptive_count == 0:
        raise ModelOutputError("question_required", stage="adaptive_question")

    return _build_assessment(turn, chains, searcher)


def _emergency_result(rule: str) -> TurnResult:
    return TurnResult(
        kind="emergency_notice",
        reply=EMERGENCY_NOTICE,
        emergency_rule=rule,
    )


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
    assessment = _ground_assessment(draft, evidence, _owner_report_summary(turn))
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
    draft: AssessmentDraft,
    evidence: list[EvidenceItem],
    owner_report_summary: list[str],
) -> Assessment:
    evidence_by_id = {item.source_id: item for item in evidence}
    referenced_ids: set[str] = set()
    for collection in (
        draft.possible_areas,
        draft.suggested_actions,
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
        outcome=draft.outcome,
        outcome_wording=OUTCOME_WORDING[draft.outcome],
        what_you_reported=owner_report_summary,
        possible_areas=draft.possible_areas,
        suggested_actions=draft.suggested_actions,
        questions_for_veterinarian=draft.questions_for_veterinarian,
        sources=sources,
        disclaimer=ASSESSMENT_SUFFIX,
    )


def _owner_report_summary(turn: TurnRequest) -> list[str]:
    """Label owner-authored text without asking a model to restate it."""
    answers = [message.content for message in turn.history if message.role == "user"]
    summary = [f"Concern: {turn.intake.concern}"]
    summary.extend(
        f"{label}: {answer}"
        for label, answer in zip(STANDARD_REPORT_LABELS, answers, strict=False)
    )
    summary.extend(
        f"Additional detail {index}: {answer}"
        for index, answer in enumerate(answers[len(STANDARD_REPORT_LABELS) :], start=1)
    )
    return summary
