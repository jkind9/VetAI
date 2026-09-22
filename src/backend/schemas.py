"""The shapes a turn is made of, and the two ways one can fail.

Nothing here decides anything. These are the values that cross the backend's edges: what the
caller may send, what a model may answer, what the backend returns, and how long each piece of
text may be. The rules that use them live in `workflow.py`.

This module imports nothing from the project and nothing from LangChain, so the workflow and its
tests can run without a model library installed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# How much a turn may contain. The follow-up cap is enforced in `workflow.py`; the character
# limits bound what a caller may send and what a model may answer.

MAX_FOLLOW_UP_QUESTIONS = 2
MAX_HISTORY_MESSAGES = MAX_FOLLOW_UP_QUESTIONS * 2  # each question plus the owner's answer
MAX_CONCERN_CHARS = 1000
MAX_DURATION_CHARS = 100
MAX_MESSAGE_CHARS = 1000
MAX_REPLY_CHARS = 1200  # the model's own text, before the workflow appends the fixed suffix

Species = Literal["dog", "cat"]
YesNoUnknown = Literal["yes", "no", "unknown"]
SymptomPattern = Literal["constant", "intermittent", "unknown"]
Role = Literal["assistant", "user"]
TurnKind = Literal["question", "summary", "emergency_notice"]

# What the workflow asks the model for. `summary_only` means the follow-up cap is spent, so a
# question is no longer an acceptable answer.
Mode = Literal["ordinary", "summary_only"]

# Why a turn could not produce a reply. Only the first is the model answering unusably; the rest
# are the call itself failing or the workflow refusing what came back.
FailureReason = Literal[
    "invalid_model_output",
    "question_limit_violation",
    "model_call_failed",
    "timeout",
    "connection",
]


class InvalidTurnRequest(ValueError):
    """The caller sent intake or history the backend will not process.

    A planned HTTP layer maps this to 422. History is rejected rather than shortened, because its
    length is what the follow-up cap counts.
    """


class ModelOutputError(RuntimeError):
    """The model call failed, or its answer cannot be used.

    The HTTP layer maps this to one generic 503 response. `reason` and `parse_failure` are for
    backend logs or later tracking only.
    """

    def __init__(self, reason: FailureReason, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason: FailureReason = reason
        self.detail = detail

    @property
    def parse_failure(self) -> bool:
        """True when the model answered but the answer did not fit `ModelReply`.

        Derived from `reason` rather than passed in separately, so the two can never disagree.
        """
        return self.reason == "invalid_model_output"


class Intake(BaseModel):
    """The structured form the owner fills in before the chat starts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    species: Species
    # Stripping happens before the length check, so a whitespace-only concern is rejected here.
    concern: str = Field(min_length=1, max_length=MAX_CONCERN_CHARS)
    duration: str = Field(default="unknown", max_length=MAX_DURATION_CHARS)
    previous_occurrence: YesNoUnknown = "unknown"
    pattern: SymptomPattern = "unknown"

    @field_validator("duration")
    @classmethod
    def _blank_duration_means_unknown(cls, value: str) -> str:
        return value or "unknown"


class Message(BaseModel):
    """One message in the current chat: an assistant question or the owner's answer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    role: Role
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

class ModelReply(BaseModel):
    """The only shape a model may answer with.

    `emergency_notice` is deliberately absent: the workflow takes that route before any model
    call, so a model cannot put the backend on it.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    kind: Literal["question", "summary"]
    reply: str = Field(min_length=1, max_length=MAX_REPLY_CHARS)

class TurnRequest(BaseModel):
    """One turn: the intake form plus the complete current chat so far."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intake: Intake
    history: list[Message] = Field(default_factory=list)


class TurnResult(BaseModel):
    """What the workflow returns for one turn.

    `emergency_rule` names the phrase rule that fired, for a later tracking layer to record. It
    is `None` on every other kind.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TurnKind
    reply: str
    emergency_rule: str | None = None
