"""Validated values crossing the workflow, model, search, and HTTP boundaries."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from backend.questions import StandardQuestionId

STANDARD_QUESTION_COUNT = 3
MIN_ADAPTIVE_QUESTIONS = 1
MAX_ADAPTIVE_QUESTIONS = 3
MAX_QUESTION_PAIRS = STANDARD_QUESTION_COUNT + MAX_ADAPTIVE_QUESTIONS
MAX_HISTORY_MESSAGES = MAX_QUESTION_PAIRS * 2
MAX_CONCERN_CHARS = 1000
MAX_MESSAGE_CHARS = 1000
MAX_QUESTION_CHARS = 500
MAX_SEARCH_QUERY_CHARS = 120
MAX_EVIDENCE_CHARS = 4000
MAX_SECTION_ITEM_CHARS = 500

Species = Literal["dog", "cat"]
Role = Literal["assistant", "user"]
QuestionMode = Literal["question_required", "question_or_ready"]
QuestionType = Literal["standard", "adaptive"]
TurnKind = Literal["question", "assessment", "emergency_notice"]
FailureReason = Literal[
    "invalid_model_output",
    "question_required",
    "model_call_failed",
    "timeout",
    "connection",
    "unsafe_search_query",
    "search_failed",
    "insufficient_evidence",
    "ungrounded_synthesis",
]


class InvalidTurnRequest(ValueError):
    """The caller supplied a history sequence the workflow cannot trust."""


class ModelOutputError(RuntimeError):
    """A named model, query, retrieval, or grounding stage failed safely."""

    def __init__(self, reason: FailureReason, detail: str = "", *, stage: str = "workflow") -> None:
        super().__init__(f"{stage}:{reason}: {detail}" if detail else f"{stage}:{reason}")
        self.reason: FailureReason = reason
        self.detail = detail
        self.stage = stage

    @property
    def parse_failure(self) -> bool:
        return self.reason in {"invalid_model_output", "ungrounded_synthesis"}


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    species: Species
    concern: str = Field(min_length=1, max_length=MAX_CONCERN_CHARS)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    role: Role
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intake: Intake
    history: list[Message] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


class AdaptiveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    kind: Literal["question", "ready_for_search"]
    question: str | None = Field(default=None, min_length=1, max_length=MAX_QUESTION_CHARS)

    @model_validator(mode="after")
    def _question_matches_kind(self) -> AdaptiveDecision:
        if self.kind == "question" and self.question is None:
            raise ValueError("question text is required for a question decision")
        if self.kind == "ready_for_search" and self.question is not None:
            raise ValueError("ready_for_search cannot include question text")
        return self


SearchQuery = Annotated[str, Field(min_length=3, max_length=MAX_SEARCH_QUERY_CHARS)]


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    queries: list[SearchQuery] = Field(min_length=1, max_length=3)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    organisation: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=MAX_EVIDENCE_CHARS)


class GroundedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    text: str = Field(min_length=1, max_length=MAX_SECTION_ITEM_CHARS)
    source_ids: list[str] = Field(min_length=1, max_length=4)


class AssessmentDraft(BaseModel):
    """What the synthesis chain may write; it cannot supply titles or URLs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    what_you_reported: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        min_length=1, max_length=5
    )
    possible_areas: list[GroundedItem] = Field(min_length=1, max_length=3)
    useful_observations: list[GroundedItem] = Field(min_length=1, max_length=4)
    questions_for_veterinarian: list[GroundedItem] = Field(min_length=1, max_length=3)


class SourceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    source_id: str
    title: str
    url: HttpUrl
    organisation: str


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    what_you_reported: list[str]
    possible_areas: list[GroundedItem]
    useful_observations: list[GroundedItem]
    questions_for_veterinarian: list[GroundedItem]
    sources: list[SourceCitation]
    disclaimer: str


class TurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TurnKind
    reply: str | None = None
    question_type: QuestionType | None = None
    question_id: StandardQuestionId | None = None
    assessment: Assessment | None = None
    emergency_rule: str | None = None
