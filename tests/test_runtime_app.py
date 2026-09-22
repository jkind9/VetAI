"""The launched server composes real chains and approved-source search once."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app import create_runtime_app
from backend.settings import BackendSettings


def test_runtime_app_builds_chains_and_searcher_from_settings(monkeypatch) -> None:
    constructed: dict[str, Any] = {}

    class StubChains:
        def __init__(self, model: str, **kwargs: Any) -> None:
            constructed["model"] = model
            constructed["chain_kwargs"] = kwargs

    class StubSearcher:
        @classmethod
        def from_defaults(cls, **kwargs: Any):
            constructed["search_kwargs"] = kwargs
            return cls()

    monkeypatch.setattr("backend.app.OllamaChatModel", StubChains)
    monkeypatch.setattr("backend.app.ApprovedSourceSearcher", StubSearcher)
    settings = BackendSettings(
        model="gpt-oss:20b",
        base_url="http://localhost:11434",
        timeout_seconds=25,
        search_timeout_seconds=8,
        search_region="uk-en",
    )

    response = TestClient(create_runtime_app(settings)).get("/health")

    assert response.json() == {"status": "ok"}
    assert constructed == {
        "model": "gpt-oss:20b",
        "chain_kwargs": {"base_url": "http://localhost:11434/", "timeout": 25.0},
        "search_kwargs": {"timeout": 8.0, "region": "uk-en"},
    }
