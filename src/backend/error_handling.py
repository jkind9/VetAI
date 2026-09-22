"""HTTP responses for failures that occur while processing a chat turn.

The workflow's exceptions carry internal reasons. This boundary logs only those reasons and
returns stable owner-facing bodies, so routing code cannot accidentally expose diagnostics.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.schemas import InvalidTurnRequest, ModelOutputError

REQUEST_ERROR_TEXT = "Please correct the request and try again."
SERVICE_ERROR_TEXT = (
    "The assistant could not complete this response. Please try again or contact a veterinarian "
    "if concerned."
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Attach every public chat-error contract to the FastAPI application."""
    app.add_exception_handler(RequestValidationError, request_validation_error)
    app.add_exception_handler(InvalidTurnRequest, invalid_turn_request)
    app.add_exception_handler(ModelOutputError, model_output_error)
    app.add_exception_handler(Exception, unexpected_application_error)


async def request_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    """Turn FastAPI schema errors into the compact public 422 contract."""
    issues = [_schema_issue(item) for item in error.errors()]
    return JSONResponse(status_code=422, content={"error": REQUEST_ERROR_TEXT, "issues": issues})


async def invalid_turn_request(request: Request, error: InvalidTurnRequest) -> JSONResponse:
    """Normalize workflow history validation with FastAPI request validation."""
    message = str(error)
    if "must end" in message:
        issue = "Chat history must end with the owner's answer to the last question."
    elif "at most" in message:
        issue = "Chat history can contain at most twelve messages."
    else:
        issue = "Chat history messages must alternate from the assistant and owner."

    return JSONResponse(
        status_code=422,
        content={"error": REQUEST_ERROR_TEXT, "issues": [{"field": "history", "message": issue}]},
    )


async def model_output_error(request: Request, error: ModelOutputError) -> JSONResponse:
    """Hide every model/search/grounding failure behind the shared 503 response."""
    logger.warning("Chat stage rejected: stage=%s reason=%s", error.stage, error.reason)
    return handle_failure(503)


async def unexpected_application_error(request: Request, error: Exception) -> JSONResponse:
    """Keep application diagnostics in server logs while returning the same safe text."""
    logger.exception("Unexpected application failure")
    return handle_failure(500)


def handle_failure(status_code: int) -> JSONResponse:
    """Return the one safe body used for failures after a request reached the application."""
    return JSONResponse(
        status_code=status_code,
        content={"error": SERVICE_ERROR_TEXT, "run_id": None},
    )


def _schema_issue(error: dict[str, Any]) -> dict[str, str]:
    """Name the invalid field without including owner text in the response."""
    location = error["loc"]
    field = ".".join(str(part) for part in location if part != "body")

    if field == "intake.concern" and error["type"] == "string_too_short":
        message = "Enter a concern."
    elif field.startswith("history"):
        field = "history"
        message = "Correct the chat history and try again."
    else:
        message = "Enter a valid value."

    return {"field": field, "message": message}
