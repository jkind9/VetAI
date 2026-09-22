"""HTTP failure contracts for a single chat turn.

The workflow owns the turn policy. These tests pin the boundary's job: turn its exceptions and
FastAPI request-validation errors into safe, stable HTTP responses without a retry or leaked text.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.error_handling import REQUEST_ERROR_TEXT, SERVICE_ERROR_TEXT
from backend.schemas import ModelOutputError
from conftest import FakeChatModel, question, summary


def _request(
    concern: str = "My dog scratched one ear today.", *, history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "intake": {
            "species": "dog",
            "concern": concern,
            "duration": "unknown",
            "previous_occurrence": "unknown",
            "pattern": "unknown",
        },
        "history": history or [],
    }


def _client(model: Any) -> TestClient:
    return TestClient(create_app(model), raise_server_exceptions=False)


def test_invalid_request_data_has_a_field_issue_without_calling_the_model() -> None:
    model = FakeChatModel(question())

    response = _client(model).post("/v1/chat", json=_request(concern="   "))

    assert response.status_code == 422
    assert response.json() == {
        "error": REQUEST_ERROR_TEXT,
        "issues": [{"field": "intake.concern", "message": "Enter a concern."}],
    }
    assert model.calls == []


@pytest.mark.parametrize(
    ("request_body", "field", "message"),
    [
        (
            {"intake": {"concern": "Ear scratching"}, "history": []},
            "intake.species",
            "Enter a valid value.",
        ),
        (
            _request() | {"intake": _request()["intake"] | {"species": "rabbit"}},
            "intake.species",
            "Enter a valid value.",
        ),
        (_request(concern="x" * 1001), "intake.concern", "Enter a valid value."),
        (
            _request(history=[{"role": "assistant", "content": "x" * 1001}]),
            "history",
            "Correct the chat history and try again.",
        ),
    ],
    ids=["missing_species", "unsupported_species", "overlong_concern", "overlong_history"],
)
def test_other_invalid_request_data_identifies_the_field(
    request_body: dict[str, Any], field: str, message: str
) -> None:
    model = FakeChatModel(question())

    response = _client(model).post("/v1/chat", json=request_body)

    assert response.status_code == 422
    assert response.json() == {
        "error": REQUEST_ERROR_TEXT,
        "issues": [{"field": field, "message": message}],
    }
    assert model.calls == []


@pytest.mark.parametrize(
    ("invalid_history", "message"),
    [
        (
            [{"role": "assistant", "content": "When did it start?"}],
            "Chat history must end with the owner's answer to the last question.",
        ),
        (
            [
                {"role": "user", "content": "Yesterday"},
                {"role": "assistant", "content": "When did it start?"},
            ],
            "Chat history messages must alternate from the assistant and owner.",
        ),
        (
            [
                {"role": "assistant", "content": "Question one"},
                {"role": "user", "content": "Answer one"},
                {"role": "assistant", "content": "Question two"},
                {"role": "user", "content": "Answer two"},
                {"role": "assistant", "content": "Question three"},
                {"role": "user", "content": "Answer three"},
            ],
            "Chat history can contain at most four messages.",
        ),
    ],
    ids=["incomplete", "out_of_order", "too_long"],
)
def test_invalid_history_has_a_history_issue_without_calling_the_model(
    invalid_history: list[dict[str, str]], message: str
) -> None:
    model = FakeChatModel(question())

    response = _client(model).post("/v1/chat", json=_request(history=invalid_history))

    assert response.status_code == 422
    assert response.json() == {
        "error": REQUEST_ERROR_TEXT,
        "issues": [{"field": "history", "message": message}],
    }
    assert model.calls == []


@pytest.mark.parametrize(
    "model,request_body",
    [
        (FakeChatModel({"kind": "question"}), _request()),
        (
            FakeChatModel(question("And has she eaten today?")),
            _request(
                history=[
                    {"role": "assistant", "content": "When did you notice it?"},
                    {"role": "user", "content": "Yesterday"},
                    {"role": "assistant", "content": "Is it constant?"},
                    {"role": "user", "content": "On and off"},
                ]
            ),
        ),
    ],
    ids=["invalid_model_output", "question_limit_violation"],
)
def test_unusable_model_results_share_the_fixed_service_error(
    model: Any, request_body: dict[str, Any]
) -> None:
    response = _client(model).post("/v1/chat", json=request_body)

    assert response.status_code == 503
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}
    assert len(model.calls) == 1


@pytest.mark.parametrize("reason", ["timeout", "connection", "model_call_failed"])
def test_provider_failures_share_the_fixed_service_error(reason: str) -> None:
    class FailingModel:
        def propose(self, turn: Any, mode: Any) -> Any:
            raise ModelOutputError(reason)

    response = _client(FailingModel()).post("/v1/chat", json=_request())

    assert response.status_code == 503
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}


def test_unexpected_application_errors_hide_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_run_turn(turn: Any, model: Any) -> Any:
        raise RuntimeError("provider key: secret diagnostic")

    monkeypatch.setattr("backend.app.run_turn", broken_run_turn)

    response = _client(FakeChatModel(question())).post("/v1/chat", json=_request())

    assert response.status_code == 500
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}
    assert "secret diagnostic" not in response.text


def test_successful_question_summary_and_emergency_results_remain_successful() -> None:
    question_response = _client(FakeChatModel(question())).post("/v1/chat", json=_request())
    summary_response = _client(FakeChatModel(summary())).post("/v1/chat", json=_request())
    emergency_response = _client(FakeChatModel(question())).post(
        "/v1/chat", json=_request("My dog is struggling to breathe.")
    )

    assert question_response.json() == {
        "reply": "When did you first notice it?",
        "kind": "question",
        "run_id": None,
    }
    assert summary_response.status_code == 200
    assert summary_response.json()["kind"] == "summary"
    assert emergency_response.json()["kind"] == "emergency_notice"


def test_health_does_not_call_a_model() -> None:
    model = FakeChatModel(question())

    response = _client(model).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert model.calls == []
