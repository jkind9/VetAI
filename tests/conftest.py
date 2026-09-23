"""Shared fakes for deterministic workflow, API, and desktop tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Every MLflow run the tests make goes to a throwaway database, never the project's mlflow.db.
# This has to happen here, before any test imports backend.app, which starts tracking on import.
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:///" + Path(tempfile.mkdtemp(), "mlflow.db").as_posix()

import pytest
from PySide6.QtWidgets import QApplication

from backend.questions import STANDARD_QUESTIONS
from backend.schemas import (
    AdaptiveDecision,
    AssessmentDraft,
    EvidenceItem,
    GroundedItem,
    Intake,
    Message,
    QuestionMode,
    SearchPlan,
    TurnRequest,
)


@pytest.fixture(scope="session")
def qapplication() -> QApplication:
    return QApplication.instance() or QApplication([])


def evidence(
    source_id: str = "S1",
    *,
    title: str = "Ear concerns in dogs",
    url: str = "https://vet.cornell.edu/example",
    organisation: str = "Cornell University College of Veterinary Medicine",
    excerpt: str = "Recording timing and visible changes can help a veterinarian.",
) -> EvidenceItem:
    return EvidenceItem(
        source_id=source_id,
        title=title,
        url=url,
        organisation=organisation,
        excerpt=excerpt,
    )


def assessment_draft(
    source_id: str = "S1", *, outcome: str = "possible_problem"
) -> AssessmentDraft:
    return AssessmentDraft(
        outcome=outcome,
        possible_areas=(
            [
                GroundedItem(
                    text="A veterinarian may consider irritation or inflammation.",
                    source_ids=[source_id],
                )
            ]
            if outcome == "possible_problem"
            else []
        ),
        suggested_actions=[
            GroundedItem(
                text=(
                    "Record when the episode happens and share the pattern with your "
                    "veterinarian."
                ),
                source_ids=[source_id],
            )
        ],
        questions_for_veterinarian=[
            GroundedItem(
                text="What changes would be most useful to monitor?",
                source_ids=[source_id],
            )
        ],
    )


class FakeChains:
    """Stage-aware stand-in whose queues make every chain invocation explicit."""

    def __init__(
        self,
        *,
        adaptive: list[Any] | None = None,
        plans: list[Any] | None = None,
        assessments: list[Any] | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.adaptive_replies = list(
            adaptive
            if adaptive is not None
            else [
                AdaptiveDecision(
                    kind="question", question="What other changes have you noticed?"
                )
            ]
        )
        self.plan_replies = list(
            plans if plans is not None else [SearchPlan(queries=["dog ear scratching veterinary"])]
        )
        self.assessment_replies = list(
            assessments if assessments is not None else [assessment_draft()]
        )
        self.adaptive_calls: list[tuple[TurnRequest, QuestionMode]] = []
        self.plan_calls: list[TurnRequest] = []
        self.synthesis_calls: list[tuple[TurnRequest, list[EvidenceItem]]] = []
        self.events = events if events is not None else []

    def propose_adaptive_question(self, turn: TurnRequest, mode: QuestionMode) -> Any:
        self.events.append("adaptive")
        self.adaptive_calls.append((turn, mode))
        if not self.adaptive_replies:
            raise AssertionError("unexpected adaptive-chain call")
        reply = self.adaptive_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def generate_search_plan(self, turn: TurnRequest) -> Any:
        self.events.append("plan")
        self.plan_calls.append(turn)
        if not self.plan_replies:
            raise AssertionError("unexpected search-plan call")
        reply = self.plan_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def synthesise_assessment(self, turn: TurnRequest, items: list[EvidenceItem]) -> Any:
        self.events.append("synthesis")
        self.synthesis_calls.append((turn, items))
        if not self.assessment_replies:
            raise AssertionError("unexpected synthesis call")
        reply = self.assessment_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeSearcher:
    def __init__(
        self,
        results: list[EvidenceItem] | None = None,
        *,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.results = list(results if results is not None else [evidence()])
        self.error = error
        self.calls: list[SearchPlan] = []
        self.events = events if events is not None else []

    def search(self, plan: SearchPlan) -> list[EvidenceItem]:
        self.events.append("search")
        self.calls.append(plan)
        if self.error is not None:
            raise self.error
        return list(self.results)


def intake(concern: str = "My dog scratched one ear today.", **overrides: Any) -> Intake:
    fields: dict[str, Any] = {"species": "dog", "concern": concern}
    fields.update(overrides)
    return Intake(**fields)


def history(*pairs: tuple[str, str]) -> list[Message]:
    messages: list[Message] = []
    for asked, answered in pairs:
        messages.extend(
            [Message(role="assistant", content=asked), Message(role="user", content=answered)]
        )
    return messages


def standard_history(
    duration: str = "Since this morning",
    previous: str = "No",
    pattern: str = "It comes and goes",
) -> list[Message]:
    return history(
        (STANDARD_QUESTIONS[0].text, duration),
        (STANDARD_QUESTIONS[1].text, previous),
        (STANDARD_QUESTIONS[2].text, pattern),
    )


def ready_history(*adaptive_pairs: tuple[str, str]) -> list[Message]:
    return standard_history() + history(*adaptive_pairs)


def assessment_payload() -> dict[str, Any]:
    """An `assessment` object exactly as the API sends it to the clients."""
    return {
        "outcome": "possible_problem",
        "outcome_wording": "The information reviewed raised points to discuss with a veterinarian.",
        "what_you_reported": ["Concern: My dog keeps scratching", "Duration: Two days"],
        "possible_areas": [{"text": "Skin irritation", "source_ids": ["S1"]}],
        "suggested_actions": [{"text": "Note when the scratching happens.", "source_ids": ["S1"]}],
        "questions_for_veterinarian": [{"text": "What should I watch for?", "source_ids": ["S1"]}],
        "sources": [
            {
                "source_id": "S1",
                "title": "Itchy skin in dogs",
                "url": "https://vet.cornell.edu/itchy-skin",
                "organisation": "Cornell University College of Veterinary Medicine",
            }
        ],
        "disclaimer": (
            "This is not a diagnosis. Please discuss your pet's concern with a veterinarian."
        ),
    }
