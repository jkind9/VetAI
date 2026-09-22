"""The desktop's HTTP boundary maps server and connection responses without a retry."""

from __future__ import annotations

import pytest
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from frontend.api_client import SERVICE_ERROR_TEXT, ChatApiClient, connection_error, parse_response


def test_successful_response_keeps_the_reply_and_kind() -> None:
    result = parse_response(200, b'{"reply":"When did it start?","kind":"question","run_id":null}')

    assert result.reply == "When did it start?"
    assert result.kind == "question"
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


def test_malformed_success_body_is_not_shown_to_the_owner() -> None:
    assert parse_response(200, b"not json").error == SERVICE_ERROR_TEXT
    assert parse_response(200, b'{"kind":"question"}').error == SERVICE_ERROR_TEXT


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
    def __init__(self, error: QNetworkReply.NetworkError, status: int = 200) -> None:
        self.finished = _FinishedSignal()
        self._error = error
        self._status = status
        self.deleted = False

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def attribute(self, attribute: QNetworkRequest.Attribute) -> int:
        return self._status

    def readAll(self) -> bytes:
        return b'{"reply":"When did it start?","kind":"question","run_id":null}'

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
    client = ChatApiClient("http://127.0.0.1:8000")
    received = []
    client.result_ready.connect(lambda request_id, result: received.append((request_id, result)))

    client._finished(8, _Reply(network_error))

    assert received[0][0] == 8
    assert received[0][1].error == message
