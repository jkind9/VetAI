"""The desktop's HTTP boundary maps server and connection responses without a retry."""

from __future__ import annotations

import json

import pytest
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from conftest import assessment_payload
from frontend.local.api_client import (
    SERVICE_ERROR_TEXT,
    ChatApiClient,
    connection_error,
    parse_response,
)

QUESTION_BODY = b'{"reply":"When did it start?","kind":"question","run_id":null}'


def _assessment_body(assessment: object) -> bytes:
    return json.dumps({"kind": "assessment", "reply": None, "assessment": assessment}).encode()


def test_successful_response_keeps_the_reply_and_kind() -> None:
    result = parse_response(200, QUESTION_BODY)

    assert result.reply == "When did it start?"
    assert result.kind == "question"
    assert result.error is None


def test_assessment_response_keeps_the_structured_result() -> None:
    result = parse_response(200, _assessment_body(assessment_payload()))

    assert result.kind == "assessment"
    assert result.assessment == assessment_payload()
    assert result.error is None


def _without(field: str) -> dict[str, object]:
    assessment = assessment_payload()
    del assessment[field]
    return assessment


def _with(field: str, value: object) -> dict[str, object]:
    return {**assessment_payload(), field: value}


@pytest.mark.parametrize(
    "assessment",
    [
        None,
        _without("sources"),
        _with("suggested_actions", "Note when it happens."),
        _with(
            "sources",
            [{**assessment_payload()["sources"][0], "url": "http://vet.cornell.edu/itchy-skin"}],
        ),
        _with("outcome", "all_clear"),
    ],
)
def test_malformed_assessment_is_not_shown_to_the_owner(assessment: object) -> None:
    assert parse_response(200, _assessment_body(assessment)).error == SERVICE_ERROR_TEXT


def test_assessment_without_sources_keeps_its_search_notice() -> None:
    assessment = {
        **assessment_payload(),
        "sources": [],
        "search_notice": "The source search did not work.",
    }

    result = parse_response(200, _assessment_body(assessment))

    assert result.assessment == assessment
    assert result.error is None


def test_validation_response_keeps_issues_for_field_correction() -> None:
    result = parse_response(
        422,
        b'{"error":"Please correct the request and try again.",'
        b'"issues":[{"field":"intake.concern","message":"Enter a concern."}]}',
    )

    assert result.issues == [{"field": "intake.concern", "message": "Enter a concern."}]
    assert result.error is None


def test_service_and_unexpected_responses_hide_server_error_bodies() -> None:
    service_error = parse_response(503, b'{"error":"provider diagnostics"}')
    unexpected_error = parse_response(500, b'{"error":"traceback"}')

    assert service_error.error == SERVICE_ERROR_TEXT
    assert unexpected_error.error == SERVICE_ERROR_TEXT


@pytest.mark.parametrize("body", [b"not json", b'{"kind":"question"}', b"[]", b'"question"'])
def test_malformed_success_body_is_not_shown_to_the_owner(body: bytes) -> None:
    assert parse_response(200, body).error == SERVICE_ERROR_TEXT


def test_connection_failure_has_a_clear_local_message() -> None:
    assert connection_error(is_timeout=True) == "The request timed out. Please try again."
    assert connection_error(is_timeout=False) == (
        "Could not reach the assistant service. Please try again."
    )


class _FinishedSignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _Reply:
    """A stand-in for QNetworkReply. `status` is None when no HTTP response arrived at all."""

    def __init__(
        self,
        error: QNetworkReply.NetworkError,
        status: int | None = 200,
        body: bytes = QUESTION_BODY,
    ) -> None:
        self.finished = _FinishedSignal()
        self._error = error
        self._status = status
        self._body = body
        self.deleted = False

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def attribute(self, attribute: QNetworkRequest.Attribute) -> int | None:
        return self._status

    def readAll(self) -> bytes:
        return self._body

    def deleteLater(self) -> None:
        self.deleted = True


class _Manager:
    def __init__(self, reply: _Reply) -> None:
        self.reply = reply
        self.url = ""
        self.payload = b""

    def post(self, request: QNetworkRequest, payload: bytes) -> _Reply:
        self.url = request.url().toString()
        self.payload = bytes(payload)
        return self.reply


def _finish(reply: _Reply, request_id: int = 8) -> list[tuple[int, object]]:
    client = ChatApiClient("http://127.0.0.1:8000")
    received = []
    client.result_ready.connect(lambda request_id, result: received.append((request_id, result)))
    client._finished(request_id, reply)
    return received


def test_client_posts_once_and_emits_its_parsed_result(qapplication) -> None:
    reply = _Reply(QNetworkReply.NetworkError.NoError)
    manager = _Manager(reply)
    client = ChatApiClient("http://127.0.0.1:8000")
    client._manager = manager
    received = []
    client.result_ready.connect(lambda request_id, result: received.append((request_id, result)))

    client.send(7, {"intake": {}, "history": []})
    reply.finished.callback()

    assert manager.url == "http://127.0.0.1:8000/v1/chat"
    assert manager.payload == b'{"intake": {}, "history": []}'
    assert received[0][0] == 7
    assert received[0][1].kind == "question"
    assert reply.deleted is True


@pytest.mark.parametrize(
    ("network_error", "message"),
    [
        (QNetworkReply.NetworkError.TimeoutError, "The request timed out. Please try again."),
        (
            QNetworkReply.NetworkError.ConnectionRefusedError,
            "Could not reach the assistant service. Please try again.",
        ),
    ],
)
def test_client_maps_no_response_failures(network_error, message, qapplication) -> None:
    received = _finish(_Reply(network_error, status=None))

    assert received[0][0] == 8
    assert received[0][1].error == message


def test_client_shows_the_issues_of_a_422_reply(qapplication) -> None:
    body = (
        b'{"error":"Please correct the request and try again.",'
        b'"issues":[{"field":"history","message":"Correct the chat history and try again."}]}'
    )
    reply = _Reply(QNetworkReply.NetworkError.UnknownContentError, status=422, body=body)

    received = _finish(reply)

    assert received[0][1].error is None
    assert received[0][1].issues == [
        {"field": "history", "message": "Correct the chat history and try again."}
    ]


def test_client_shows_the_service_text_for_a_503_reply(qapplication) -> None:
    body = b'{"error":"provider diagnostics","run_id":null}'
    reply = _Reply(QNetworkReply.NetworkError.ServiceUnavailableError, status=503, body=body)

    received = _finish(reply)

    assert received[0][1].error == SERVICE_ERROR_TEXT
