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
from mlflow_tracking.chat_runs import run_tracked_turn, start_tracking


def create_app(
    chains: Any, searcher: Any, run_params: dict[str, str] | None = None
) -> FastAPI:
    """Build an API with injected chain and search boundaries for deterministic tests.

    Every turn is recorded as an MLflow run, with `run_params` (for example the model name) added
    to each run's parameters.
    """
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat")
    def chat(turn: TurnRequest) -> dict[str, Any]:
        result, run_id = run_tracked_turn(turn, chains, searcher, run_params or {})
        payload = result.model_dump(mode="json", exclude={"emergency_rule"})
        payload["run_id"] = run_id
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
        structured_output_method=settings.structured_output_method,
        reasoning=settings.reasoning,
    )
    searcher = ApprovedSourceSearcher.from_defaults(
        timeout=settings.search_timeout_seconds,
        region=settings.search_region,
    )
    start_tracking()
    # Recorded on every run: the model, and a SHA-256 of each of the four prompt files.
    run_params = {"model": settings.model} | chains.prompt_hashes
    return create_app(chains, searcher, run_params)


app = create_runtime_app()
