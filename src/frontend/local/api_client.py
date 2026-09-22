"""The desktop's one-shot HTTP client for the local backend."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from PySide6.QtCore import QByteArray, QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

REQUEST_ERROR_TEXT = "Please correct the request and try again."
SERVICE_ERROR_TEXT = (
    "The assistant could not complete this response. Please try again or contact a veterinarian "
    "if concerned."
)

ReplyKind = Literal["question", "summary", "emergency_notice"]


@dataclass(frozen=True)
class ApiResult:
    """The information the Qt window needs after one HTTP attempt."""

    kind: ReplyKind | None = None
    reply: str | None = None
    issues: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None


def parse_response(status: int, body: bytes) -> ApiResult:
    """Parse only the public API contract; unexpected bodies never reach the owner."""
    try:
        payload = json.loads(body)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return ApiResult(error=SERVICE_ERROR_TEXT)

    if status == 200:
        kind = payload.get("kind")
        reply = payload.get("reply")
        if kind in {"question", "summary", "emergency_notice"} and isinstance(reply, str):
            return ApiResult(kind=kind, reply=reply)
        return ApiResult(error=SERVICE_ERROR_TEXT)

    if status == 422:
        issues = payload.get("issues")
        if isinstance(issues, list):
            public_issues = [
                {"field": item["field"], "message": item["message"]}
                for item in issues
                if isinstance(item, dict)
                and isinstance(item.get("field"), str)
                and isinstance(item.get("message"), str)
            ]
            if public_issues:
                return ApiResult(issues=public_issues)
        return ApiResult(error=REQUEST_ERROR_TEXT)

    return ApiResult(error=SERVICE_ERROR_TEXT)


def connection_error(*, is_timeout: bool) -> str:
    """Describe a no-response failure without guessing whether the backend processed the turn."""
    if is_timeout:
        return "The request timed out. Please try again."
    return "Could not reach the assistant service. Please try again."


class ChatApiClient(QObject):
    """Post a single turn asynchronously. Retries are always initiated by the owner in the UI."""

    result_ready = Signal(int, object)

    def __init__(self, base_url: str, *, timeout_ms: int = 65_000) -> None:
        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._timeout_ms = timeout_ms
        self._manager = QNetworkAccessManager(self)

    def send(self, request_id: int, turn: dict[str, Any]) -> None:
        """Start one request. The caller decides if and when a failed turn is retried."""
        request = QNetworkRequest(QUrl(f"{self._base_url}/v1/chat"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(self._timeout_ms)
        payload = QByteArray(json.dumps(turn).encode("utf-8"))
        reply = self._manager.post(request, payload)
        reply.finished.connect(lambda: self._finished(request_id, reply))

    def _finished(self, request_id: int, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            is_timeout = reply.error() == QNetworkReply.NetworkError.TimeoutError
            result = ApiResult(error=connection_error(is_timeout=is_timeout))
        else:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            result = parse_response(int(status or 0), bytes(reply.readAll()))

        self.result_ready.emit(request_id, result)
        reply.deleteLater()
