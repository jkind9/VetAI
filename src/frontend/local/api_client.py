"""The desktop's one-shot HTTP client for the local backend."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from PySide6.QtCore import QByteArray, QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

REQUEST_ERROR_TEXT = "Please correct the request and try again."
SERVICE_ERROR_TEXT = (
    "The assistant could not complete this response. Please try again or contact a veterinarian "
    "if concerned."
)

ReplyKind = Literal["question", "assessment", "emergency_notice"]

OUTCOMES = ("possible_problem", "nothing_flagged")
CITED_SECTIONS = ("possible_areas", "suggested_actions", "questions_for_veterinarian")


@dataclass(frozen=True)
class ApiResult:
    """The information the Qt window needs after one HTTP attempt."""

    kind: ReplyKind | None = None
    reply: str | None = None
    assessment: dict[str, Any] | None = None
    issues: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None


def parse_response(status: int, body: bytes) -> ApiResult:
    """Parse only the public API contract; unexpected bodies never reach the owner."""
    try:
        payload = json.loads(body)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return ApiResult(error=SERVICE_ERROR_TEXT)
    if not isinstance(payload, dict):
        return ApiResult(error=SERVICE_ERROR_TEXT)

    if status == 200:
        kind = payload.get("kind")
        if kind == "assessment" and _is_assessment(payload.get("assessment")):
            return ApiResult(kind=kind, assessment=payload["assessment"])
        if kind in ("question", "emergency_notice") and _is_text(payload.get("reply")):
            return ApiResult(kind=kind, reply=payload["reply"])
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


def _is_assessment(value: object) -> bool:
    """True when every field the window shows is present with the right type."""
    if not isinstance(value, dict) or value.get("outcome") not in OUTCOMES:
        return False
    if not (_is_text(value.get("outcome_wording")) and _is_text(value.get("disclaimer"))):
        return False
    if not _is_list_of(value.get("what_you_reported"), _is_text):
        return False
    if value.get("search_notice") is not None and not _is_text(value["search_notice"]):
        return False
    if not all(_is_list_of(value.get(section), _is_cited_item) for section in CITED_SECTIONS):
        return False
    return _is_list_of(value.get("sources"), _is_source)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_list_of(value: object, is_item: Callable[[object], bool]) -> bool:
    return isinstance(value, list) and all(is_item(item) for item in value)


def _is_cited_item(value: object) -> bool:
    return (
        isinstance(value, dict)
        and _is_text(value.get("text"))
        and _is_list_of(value.get("source_ids"), _is_text)
    )


def _is_source(value: object) -> bool:
    # The window turns each source into a clickable link, so only https:// addresses are allowed.
    return (
        isinstance(value, dict)
        and all(_is_text(value.get(key)) for key in ("source_id", "title", "organisation"))
        and _is_text(value.get("url"))
        and value["url"].startswith("https://")
    )


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
        # Qt reports an error for every 4xx and 5xx reply too, so the HTTP status, not
        # reply.error(), tells us whether the backend answered at all.
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status is None:
            is_timeout = reply.error() == QNetworkReply.NetworkError.TimeoutError
            result = ApiResult(error=connection_error(is_timeout=is_timeout))
        else:
            result = parse_response(int(status), bytes(reply.readAll()))

        self.result_ready.emit(request_id, result)
        reply.deleteLater()
