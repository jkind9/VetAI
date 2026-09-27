"""Emergency-first state machine for the bounded multi-chain conversation."""

from __future__ import annotations

import logging
import re
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
    EmergencyCheck,
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

SEARCH_UNAVAILABLE_NOTICE = (
    "The source search did not work, so this result is based on general guidance and has no "
    "linked sources."
)

# Search-provider outcomes that still let the summary go ahead without sources. An unsafe query
# is a model fault, so it still fails the turn.
_RECOVERABLE_SEARCH_FAILURES = {"search_failed", "no_search_results", "insufficient_evidence"}

STANDARD_REPORT_LABELS =("Duration", "Previous occurrence", "Pattern")
_SEMANTIC_REPEAT_PATTERNS = (re.compile(r"\b(?:age|how old)\b", re.IGNORECASE),)

TModel = TypeVar("TModel", bound=BaseModel)

logger = logging.getLogger(__name__)


def run_turn(turn: TurnRequest, chains: Any, searcher: Any) -> TurnResult:
    """Advance one safe state using deterministic policy around four model chains."""
    _validate_history(turn.history)

    emergency = find_emergency(_owner_written_text(turn))
    if emergency is not None:
        return _emergency_result(emergency.rule)

    raw_emergency_check = _call_stage(
        "emergency_check", chains.check_for_emergency, turn
    )
    emergency_check = _validate_chain_output(
        EmergencyCheck, raw_emergency_check, stage="emergency_check"
    )
    if emergency_check.emergency:
        return _emergency_result("model_emergency_check")

    completed_pairs = len(turn.history) // 2
    standard = next_standard_question(completed_pairs)
    if standard is not None:
        return TurnResult(
            kind="question",
            reply=standard.text,
            question_type="standard",
            question_id=standard.id,
        )

    # The follow-up questions are a loop the code counts, one pass per HTTP turn: the count comes
    # from the history the client sends. After the last pass the model is not asked again, so it
    # cannot ask a fourth question.
    adaptive_count = completed_pairs - STANDARD_QUESTION_COUNT
    if adaptive_count < MAX_ADAPTIVE_QUESTIONS:
        mode: QuestionMode = "question_required" if adaptive_count == 0 else "question_or_ready"
        raw_decision = _call_stage(
            "adaptive_question", chains.propose_adaptive_question, turn, mode
        )
        decision = _validate_chain_output(
            AdaptiveDecision, raw_decision, stage="adaptive_question"
        )
        if decision.kind == "question" and not _question_was_already_asked(
            decision.question, turn.history
        ):
            return TurnResult(
                kind="question",
                reply=decision.question,
                question_type="adaptive",
            )
        if adaptive_count == 0:
            raise ModelOutputError("question_required", stage="adaptive_question")

    return _build_assessment(turn, chains, searcher)


def _question_was_already_asked(
    question: str | None, history: list[Message]
) -> bool:
    if question is None:
        return False
    normalised = question.casefold()
    return any(
        message.role == "assistant"
        and (
            message.content.casefold() == normalised
            or any(
                pattern.search(question) and pattern.search(message.content)
                for pattern in _SEMANTIC_REPEAT_PATTERNS
            )
        )
        for message in history
    )


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

    evidence = _search_or_nothing(searcher, plan)

    raw_draft = _call_stage(
        "evidence_synthesis", chains.synthesise_assessment, turn, evidence
    )
    draft = _validate_chain_output(
        AssessmentDraft, raw_draft, stage="evidence_synthesis"
    )
    assessment = _ground_assessment(draft, evidence, _owner_report_summary(turn))
    return TurnResult(kind="assessment", assessment=assessment)


def _search_or_nothing(searcher: Any, plan: SearchPlan) -> list[EvidenceItem]:
    """Return the evidence, or an empty list when the search provider let us down."""
    try:
        return list(searcher.search(plan))
    except ModelOutputError as error:
        if error.reason not in _RECOVERABLE_SEARCH_FAILURES:
            raise
        logger.warning("search unavailable, continuing without sources: %s", error)
    except Exception as error:  # search implementations must not leak provider exceptions
        logger.warning(
            "search unavailable, continuing without sources: %s", type(error).__name__
        )
    return []


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
    if evidence and any(
        not grounded.source_ids
        for collection in (
            draft.possible_areas,
            draft.suggested_actions,
            draft.questions_for_veterinarian,
        )
        for grounded in collection
    ):
        raise ModelOutputError(
            "ungrounded_synthesis",
            "an item cited no source although sources were found",
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
        search_notice=None if evidence else SEARCH_UNAVAILABLE_NOTICE,
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
