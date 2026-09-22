"""The desktop's HTTP boundary maps server and connection responses without a retry."""

from __future__ import annotations

from frontend.api_client import SERVICE_ERROR_TEXT, connection_error, parse_response


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


def test_connection_failure_has_a_clear_local_message() -> None:
    assert connection_error(is_timeout=True) == "The request timed out. Please try again."
    assert connection_error(is_timeout=False) == "Could not reach the assistant service. Please try again."
