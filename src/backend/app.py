"""The small HTTP boundary for one chat turn.

The workflow decides the outcome. This module only accepts a request, calls that workflow once,
and translates failures into the stable responses the desktop can act on.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.error_handling import register_error_handlers
from backend.schemas import TurnRequest
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
