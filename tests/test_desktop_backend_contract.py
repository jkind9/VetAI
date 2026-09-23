"""The desktop's real requests, sent to the real backend code, and its parsing of every reply.

These tests exist because the desktop once drifted from the backend unnoticed: its own tests
passed while its first request was refused and it could not show an assessment.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.questions import STANDARD_QUESTIONS
from backend.schemas import AdaptiveDecision, ModelOutputError
from backend.workflow import EMERGENCY_NOTICE
from conftest import FakeChains, FakeSearcher, evidence
from frontend.local.api_client import SERVICE_ERROR_TEXT, ApiResult, parse_response
from frontend.local.app import ChatState, accept, request_body, start_chat

STANDARD_ANSWERS = ("Two days", "No", "It comes and goes")


def _send(client: TestClient, state: ChatState) -> ApiResult:
    response = client.post("/v1/chat", json=request_body(state))
    return parse_response(response.status_code, response.content)


def _answer_standard_questions(client: TestClient, state: ChatState) -> ChatState:
    """Send the concern and answer the three standard questions, as the window would."""
    for answer in STANDARD_ANSWERS:
        state = replace(accept(state, _send(client, state)), draft_answer=answer)
    return state


def test_first_desktop_request_is_accepted() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher()))

    result = _send(client, start_chat("dog", "My dog keeps scratching"))

    assert result.error is None
    assert result.kind == "question"
    assert result.reply == STANDARD_QUESTIONS[0].text


def test_desktop_reads_a_real_assessment() -> None:
    chains = FakeChains(
        adaptive=[
            AdaptiveDecision(kind="question", question="Is the skin red?"),
            AdaptiveDecision(kind="ready_for_search"),
        ]
    )
    client = TestClient(create_app(chains, FakeSearcher()))
    state = _answer_standard_questions(client, start_chat("dog", "My dog keeps scratching"))
    state = replace(accept(state, _send(client, state)), draft_answer="A little red")

    result = _send(client, state)

    assert result.kind == "assessment"
    assert result.assessment["sources"][0]["url"] == str(evidence().url)
    assert accept(state, result).ended is True


def test_desktop_reads_a_real_emergency_notice() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher()))
    state = start_chat("dog", "She is struggling to breathe")

    result = _send(client, state)

    assert result.kind == "emergency_notice"
    assert result.reply == EMERGENCY_NOTICE
    assert accept(state, result).ended is True


def test_desktop_shows_a_real_422_as_field_issues() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher()))
    body = request_body(start_chat("dog", "My dog keeps scratching"))
    body["history"] = [{"role": "user", "content": "An answer with no question before it"}]

    response = client.post("/v1/chat", json=body)
    result = parse_response(response.status_code, response.content)

    assert response.status_code == 422
    assert result.error is None
    assert result.issues[0]["field"] == "history"


def test_desktop_shows_a_real_503_as_the_service_text() -> None:
    chains = FakeChains(adaptive=[ModelOutputError("timeout", stage="adaptive_question")])
    client = TestClient(create_app(chains, FakeSearcher()))
    state = _answer_standard_questions(client, start_chat("dog", "My dog keeps scratching"))

    result = _send(client, state)

    assert result.error == SERVICE_ERROR_TEXT
