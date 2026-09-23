"""HTTP contracts for standard questions, grounded assessment, and safe failures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import _serve_browser_client, create_app
from backend.error_handling import REQUEST_ERROR_TEXT, SERVICE_ERROR_TEXT
from backend.schemas import AdaptiveDecision, ModelOutputError
from conftest import FakeChains, FakeSearcher, ready_history


def _request(
    concern: str = "My dog scratched one ear today.",
    *,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "intake": {"species": "dog", "concern": concern},
        "history": history or [],
    }


def _client(chains: Any | None = None, searcher: Any | None = None) -> TestClient:
    return TestClient(
        create_app(chains or FakeChains(), searcher or FakeSearcher()),
        raise_server_exceptions=False,
    )


def test_first_request_returns_the_first_standard_question() -> None:
    response = _client().post("/v1/chat", json=_request())

    assert response.status_code == 200
    assert response.json() == {
        "kind": "question",
        "reply": "How long has this been happening?",
        "question_type": "standard",
        "question_id": "duration",
        "assessment": None,
        "run_id": None,
    }


def test_completed_questioning_returns_structured_assessment() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    history_payload = [item.model_dump() for item in ready_history(("Any discharge?", "No"))]

    response = _client(chains).post(
        "/v1/chat", json=_request(history=history_payload)
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["kind"] == "assessment"
    assert payload["reply"] is None
    assert payload["assessment"]["what_you_reported"]
    assert payload["assessment"]["outcome"] == "possible_problem"
    assert payload["assessment"]["outcome_wording"]
    assert payload["assessment"]["possible_areas"][0]["source_ids"] == ["S1"]
    assert payload["assessment"]["suggested_actions"][0]["source_ids"] == ["S1"]
    assert payload["assessment"]["sources"][0]["url"] == "https://vet.cornell.edu/example"
    assert payload["run_id"] is None


def test_invalid_intake_is_a_field_correction_without_downstream_calls() -> None:
    chains = FakeChains()
    searcher = FakeSearcher()

    response = _client(chains, searcher).post("/v1/chat", json=_request(concern="   "))

    assert response.status_code == 422
    assert response.json() == {
        "error": REQUEST_ERROR_TEXT,
        "issues": [{"field": "intake.concern", "message": "Enter a concern."}],
    }
    assert chains.adaptive_calls == []
    assert searcher.calls == []


def test_invalid_standard_prefix_is_a_history_correction() -> None:
    response = _client().post(
        "/v1/chat",
        json=_request(
            history=[
                {"role": "assistant", "content": "A different first question?"},
                {"role": "user", "content": "Today"},
            ]
        ),
    )

    assert response.status_code == 422
    assert response.json()["issues"][0]["field"] == "history"


def test_model_and_search_failures_share_the_fixed_service_error() -> None:
    class FailingChains(FakeChains):
        def propose_adaptive_question(self, turn, mode):
            raise ModelOutputError("timeout", stage="adaptive_question")

    history_payload = [item.model_dump() for item in ready_history()]
    response = _client(FailingChains()).post(
        "/v1/chat", json=_request(history=history_payload)
    )

    assert response.status_code == 503
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}


def test_health_calls_neither_chains_nor_search() -> None:
    chains = FakeChains()
    searcher = FakeSearcher()

    response = _client(chains, searcher).get("/health")

    assert response.json() == {"status": "ok"}
    assert chains.adaptive_calls == []
    assert searcher.calls == []


def test_built_browser_client_is_served_without_shadowing_api(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>VetAI browser demo</h1>", encoding="utf-8")
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    _serve_browser_client(app, dist)
    client = TestClient(app)

    assert client.get("/").text == "<h1>VetAI browser demo</h1>"
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_browser_build_does_not_add_a_static_mount(tmp_path: Path) -> None:
    app = FastAPI()

    _serve_browser_client(app, tmp_path / "missing")

    assert all(route.name != "public_client" for route in app.routes)
