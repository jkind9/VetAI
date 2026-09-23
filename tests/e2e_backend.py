"""Deterministic hosted backend used only by the browser E2E suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Keep this server's MLflow runs out of the project's mlflow.db. This has to happen before
# importing backend.app, which starts tracking on import.
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:///" + Path(tempfile.mkdtemp(), "mlflow.db").as_posix()

from backend.app import create_app
from backend.schemas import (
    AdaptiveDecision,
    AssessmentDraft,
    EvidenceItem,
    GroundedItem,
    ModelOutputError,
    QuestionMode,
    SearchPlan,
    TurnRequest,
)

ADAPTIVE_QUESTIONS = (
    "Have you noticed weakness, vomiting, or a change in breathing?",
    "Does the panting stop while your dog is asleep?",
    "Has your dog been exposed to unusual heat or exercise?",
)


class ScenarioChains:
    """Deterministic model boundary that still exercises the production workflow."""

    def __init__(self) -> None:
        self.failed_concerns: set[str] = set()

    def propose_adaptive_question(
        self, turn: TurnRequest, mode: QuestionMode
    ) -> AdaptiveDecision:
        concern = turn.intake.concern.casefold()
        if "provider failure" in concern and concern not in self.failed_concerns:
            self.failed_concerns.add(concern)
            raise ModelOutputError(
                "model_call_failed", "deterministic E2E failure", stage="adaptive"
            )
        if "dieing" in concern:
            return AdaptiveDecision(kind="urgent_escalation")
        answered_adaptive = max(0, (len(turn.history) // 2) - 3)
        if "persistent" in concern:
            return AdaptiveDecision(
                kind="question", question=ADAPTIVE_QUESTIONS[answered_adaptive]
            )
        if mode == "question_required":
            return AdaptiveDecision(kind="question", question=ADAPTIVE_QUESTIONS[0])
        return AdaptiveDecision(kind="ready_for_search")

    def generate_search_plan(self, turn: TurnRequest) -> SearchPlan:
        return SearchPlan(queries=["dog panting at rest veterinary guidance"])

    def synthesise_assessment(
        self, turn: TurnRequest, evidence: list[EvidenceItem]
    ) -> AssessmentDraft:
        source_id = evidence[0].source_id
        settled = "settled" in turn.intake.concern.casefold()
        if settled:
            return AssessmentDraft(
                outcome="nothing_flagged",
                possible_areas=[],
                suggested_actions=[
                    GroundedItem(
                        text="Record a video if it happens again.",
                        source_ids=[source_id],
                    )
                ],
                questions_for_veterinarian=[
                    GroundedItem(
                        text="What changes would mean I should arrange an appointment?",
                        source_ids=[source_id],
                    )
                ],
            )
        return AssessmentDraft(
            outcome="possible_problem",
            possible_areas=[
                GroundedItem(
                    text="A veterinarian may consider heat, pain, or breathing-related causes.",
                    source_ids=[source_id],
                )
            ],
            suggested_actions=[
                GroundedItem(
                    text="Record a video if the panting happens again.",
                    source_ids=[source_id],
                )
            ],
            questions_for_veterinarian=[
                GroundedItem(
                    text="Does panting at rest need an examination soon?",
                    source_ids=[source_id],
                )
            ],
        )


class ScenarioSearcher:
    """Known approved evidence without network or provider variability."""

    def search(self, plan: SearchPlan) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                source_id="S1",
                title="MSD Veterinary Manual",
                url=(
                    "https://www.msdvetmanual.com/special-pet-topics/emergencies/"
                    "what-to-do-in-a-dog-or-cat-emergency"
                ),
                organisation="MSD Veterinary Manual",
                excerpt=(
                    "Rapid panting can be a sign of heat stroke. Record changes and contact a "
                    "veterinarian when concerned."
                ),
            )
        ]


app = create_app(ScenarioChains(), ScenarioSearcher())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
