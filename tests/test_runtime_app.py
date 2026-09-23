"""The launched server composes real chains and approved-source search once."""

from __future__ import annotations

from typing import Any

import mlflow
from fastapi.testclient import TestClient

from backend.app import create_runtime_app
from backend.settings import BackendSettings

STUB_PROMPT_HASHES = {
    "adaptive_question": "a1",
    "search_query": "b2",
    "evidence_synthesis": "c3",
}


def test_runtime_app_builds_chains_and_searcher_from_settings(monkeypatch) -> None:
    constructed: dict[str, Any] = {}

    class StubChains:
        prompt_hashes = STUB_PROMPT_HASHES

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


def test_runtime_app_records_the_model_and_prompt_versions_on_each_run(monkeypatch) -> None:
    class StubChains:
        prompt_hashes = STUB_PROMPT_HASHES

        def __init__(self, model: str, **kwargs: Any) -> None:
            pass

    class StubSearcher:
        @classmethod
        def from_defaults(cls, **kwargs: Any):
            return cls()

    monkeypatch.setattr("backend.app.OllamaChatModel", StubChains)
    monkeypatch.setattr("backend.app.ApprovedSourceSearcher", StubSearcher)
    client = TestClient(create_runtime_app(BackendSettings(model="gpt-oss:20b")))

    turn = {"intake": {"species": "cat", "concern": "She keeps sneezing"}, "history": []}
    run = mlflow.get_run(client.post("/v1/chat", json=turn).json()["run_id"])

    assert mlflow.get_experiment(run.info.experiment_id).name == "vetai-chat"
    assert run.data.params == {
        "model": "gpt-oss:20b",
        **STUB_PROMPT_HASHES,
        "species": "cat",
        "answered_questions": "0",
    }
