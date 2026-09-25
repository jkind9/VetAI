"""Opt-in quality evaluation for the dedicated real-model emergency check."""

from __future__ import annotations

import os

import mlflow
import pytest

from backend.model import OllamaChatModel
from backend.schemas import Intake, TurnRequest
from mlflow_tracking.chat_runs import start_tracking

pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(
        os.environ.get("VETAI_RUN_EMERGENCY_CHECK_LIVE") != "1",
        reason="set VETAI_RUN_EMERGENCY_CHECK_LIVE=1 and start Ollama",
    ),
]

MODEL_TAG = os.environ.get("VETAI_OLLAMA_MODEL", "gpt-oss:20b")
EMERGENCY_CASES = (
    "He isn't breathing properly and his gums look blue.",
    "He isn't breathing.",
    "She can’t breathe.",
    "She's collapsed in the garden.",
    "Max collapsed on the kitchen floor.",
    "My dog's passed out.",
    "Her tongue has gone blue.",
)
ORDINARY_CASES = (
    "Maybe a week.",
    "Her heart rate went up after her new medication.",
    "She isn’t having any trouble breathing.",
    "She scratched one ear today.",
    "My dog has been panting more than usual while resting.",
    "It comes and goes.",
    "No, this has never happened before.",
)


def _turn(concern: str) -> TurnRequest:
    return TurnRequest(intake=Intake(species="dog", concern=concern), history=[])


def test_real_emergency_check_catches_all_clear_cases_without_false_alarms() -> None:
    start_tracking()
    chains = OllamaChatModel(MODEL_TAG)

    with mlflow.start_run(run_name="emergency_check_live_eval"):
        emergency_results = [
            chains.check_for_emergency(_turn(case)).emergency for case in EMERGENCY_CASES
        ]
        ordinary_results = [
            chains.check_for_emergency(_turn(case)).emergency for case in ORDINARY_CASES
        ]
        emergencies_caught = sum(emergency_results)
        false_alarms = sum(ordinary_results)
        mlflow.log_param("model", MODEL_TAG)
        mlflow.log_metrics(
            {
                "emergencies_caught": emergencies_caught,
                "false_alarms": false_alarms,
                "cases": len(EMERGENCY_CASES) + len(ORDINARY_CASES),
            }
        )

        assert emergencies_caught == len(EMERGENCY_CASES)
        assert false_alarms == 0
