"""One real-model check: does the chosen local model return something the workflow accepts?

Skipped by default. Ordinary test runs and CI must not need a downloaded model or a running
service. Run it deliberately:

    VETAI_RUN_OLLAMA_SMOKE=1 uv run pytest tests/test_ollama_smoke.py -v -s

Override the model with VETAI_OLLAMA_MODEL. The assertions are about structure and routing only —
the model's wording is reviewed by a person against documentation/test-cases.md, not asserted here.
"""

from __future__ import annotations

import os

import pytest

from backend.schemas import TurnRequest
from backend.workflow import SUMMARY_SUFFIX, run_turn
from conftest import history, intake

pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(
        os.environ.get("VETAI_RUN_OLLAMA_SMOKE") != "1",
        reason="set VETAI_RUN_OLLAMA_SMOKE=1 and start Ollama to run the real-model check",
    ),
]

MODEL_TAG = os.environ.get("VETAI_OLLAMA_MODEL", "llama3:8b")


@pytest.fixture(scope="module")
def ollama_model():
    from backend.model import OllamaChatModel

    return OllamaChatModel(MODEL_TAG)


def test_a_first_turn_returns_a_usable_reply(ollama_model) -> None:
    """With no history the model may ask or recap; either must survive validation."""
    request = TurnRequest(
        intake=intake("My dog scratched one ear today.", duration="today", pattern="intermittent"),
        history=[],
    )

    result = run_turn(request, ollama_model)

    assert result.kind in {"question", "summary"}
    assert result.reply.strip()
    print(f"\n[{MODEL_TAG}] first turn -> {result.kind}: {result.reply}")


def test_summary_only_mode_ends_the_flow(ollama_model) -> None:
    """After two follow-ups the whole turn must land on a recap with the fixed suffix."""
    request = TurnRequest(
        intake=intake("My dog scratched one ear today.", duration="today"),
        history=history(
            ("When did you first notice it?", "Yesterday evening"),
            ("Is it constant or on and off?", "On and off"),
        ),
    )

    result = run_turn(request, ollama_model)

    assert result.kind == "summary"
    assert result.reply.endswith(SUMMARY_SUFFIX)
    print(f"\n[{MODEL_TAG}] summary_only -> {result.reply}")


def test_an_emergency_phrase_still_never_reaches_the_model(ollama_model) -> None:
    """The gate sits in front of the real model too, not only the stand-in."""
    request = TurnRequest(intake=intake("My dog is struggling to breathe."), history=[])

    result = run_turn(request, ollama_model)

    assert result.kind == "emergency_notice"
