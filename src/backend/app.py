"""The small HTTP boundary for one chat turn.

The workflow decides the outcome. This module only accepts a request, calls that workflow once,
and translates failures into the stable responses the desktop can act on.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.error_handling import register_error_handlers
from backend.model import OllamaChatModel
from backend.schemas import TurnRequest
from backend.settings import BackendSettings
from backend.workflow import run_turn


def create_app(model: Any) -> FastAPI:
    """Build an API whose model dependency is supplied by the process that starts it.

    Keeping the model as an argument lets HTTP tests use a fake and avoids constructing an Ollama
    client as an import side effect.
    """
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat")
    def chat(turn: TurnRequest) -> dict[str, str | None]:
        result = run_turn(turn, model)
        return {"reply": result.reply, "kind": result.kind, "run_id": None}

    return app


def create_runtime_app(settings: BackendSettings | None = None) -> FastAPI:
    """Build the app used by Uvicorn, with the model selected at process startup."""
    settings = settings or BackendSettings.from_environment()
    model = OllamaChatModel(
        settings.model,
        base_url=str(settings.base_url),
        timeout=settings.timeout_seconds,
    )
    return create_app(model)


# Uvicorn imports this object with ``backend.app:app``. Tests use ``create_app`` with a fake model.
app = create_runtime_app()
