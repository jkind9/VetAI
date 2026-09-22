"""FastAPI composition for one stateless conversation turn."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.error_handling import register_error_handlers
from backend.model import OllamaChatModel
from backend.schemas import TurnRequest
from backend.search import ApprovedSourceSearcher
from backend.settings import BackendSettings
from backend.workflow import run_turn


def create_app(chains: Any, searcher: Any) -> FastAPI:
    """Build an API with injected chain and search boundaries for deterministic tests."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat")
    def chat(turn: TurnRequest) -> dict[str, Any]:
        result = run_turn(turn, chains, searcher)
        payload = result.model_dump(mode="json", exclude={"emergency_rule"})
        payload["run_id"] = None
        return payload

    return app


def create_runtime_app(settings: BackendSettings | None = None) -> FastAPI:
    settings = settings or BackendSettings.from_environment()
    chains = OllamaChatModel(
        settings.model,
        base_url=str(settings.base_url),
        timeout=settings.timeout_seconds,
    )
    searcher = ApprovedSourceSearcher.from_defaults(
        timeout=settings.search_timeout_seconds,
        region=settings.search_region,
    )
    return create_app(chains, searcher)


app = create_runtime_app()
