"""The server entrypoint composes the real model without making a network call at import time."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app import create_runtime_app
from backend.settings import BackendSettings


def test_runtime_app_builds_the_ollama_adapter_from_settings(monkeypatch) -> None:
    constructed: dict[str, Any] = {}

    class StubOllamaModel:
        def __init__(self, model: str, **kwargs: Any) -> None:
            constructed["model"] = model
            constructed.update(kwargs)

    monkeypatch.setattr("backend.app.OllamaChatModel", StubOllamaModel)
    settings = BackendSettings(
        model="llama3:latest", base_url="http://localhost:11434", timeout_seconds=15
    )

    response = TestClient(create_runtime_app(settings)).get("/health")

    assert response.json() == {"status": "ok"}
    assert constructed == {
        "model": "llama3:latest",
        "base_url": "http://localhost:11434/",
        "timeout": 15.0,
    }
