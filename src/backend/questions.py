"""The deterministic question prefix that starts every ordinary conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StandardQuestionId = Literal["duration", "previous_occurrence", "pattern"]


@dataclass(frozen=True)
class StandardQuestion:
    id: StandardQuestionId
    text: str


STANDARD_QUESTIONS: tuple[StandardQuestion, ...] = (
    StandardQuestion("duration", "How long has this been happening?"),
    StandardQuestion("previous_occurrence", "Has this happened before?"),
    StandardQuestion("pattern", "Is it happening constantly, or does it come and go?"),
)


def next_standard_question(completed_pairs: int) -> StandardQuestion | None:
    """Return the next catalog item, or ``None`` once all three were answered."""
    if 0 <= completed_pairs < len(STANDARD_QUESTIONS):
        return STANDARD_QUESTIONS[completed_pairs]
    return None
