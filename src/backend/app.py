"""FastAPI composition for one stateless conversation turn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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

    _serve_browser_client(app)
    return app


PUBLIC_CLIENT_DIST = Path(__file__).resolve().parents[1] / "frontend" / "public" / "dist"


def _serve_browser_client(app: FastAPI, dist: Path = PUBLIC_CLIENT_DIST) -> None:
    """Serve the built Svelte page at `/`, if it has been built.

    Mounted last so `/v1/chat`, `/health` and `/docs` keep priority, and skipped when `dist/` is
    absent so the backend still starts for anyone using only the desktop client. Sharing one origin
    with the API is what removes any CORS configuration from this project.
    """
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="public_client")


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
