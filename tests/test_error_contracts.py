"""Public HTTP contracts for model, search, grounding, and application failures."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import create_app
from backend.error_handling import SERVICE_ERROR_TEXT
from backend.schemas import AdaptiveDecision, ModelOutputError
from conftest import FakeChains, FakeSearcher, assessment_draft, ready_history


def _request(*, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "intake": {"species": "dog", "concern": "My dog scratched one ear today."},
        "history": history or [],
    }


def _client(chains: Any, searcher: Any) -> TestClient:
    return TestClient(
        create_app(chains, searcher),
        raise_server_exceptions=False,
    )


def _ready_request() -> dict[str, Any]:
    return _request(
        history=[
            item.model_dump()
            for item in ready_history(("Have you noticed any other changes?", "No"))
        ]
    )


def _assert_service_error(response: Any, *, status_code: int = 503) -> None:
    assert response.status_code == status_code
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}


def test_malformed_adaptive_output_is_a_stable_503_without_downstream_calls() -> None:
    chains = FakeChains(adaptive=[{"kind": "unexpected"}])
    searcher = FakeSearcher()

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.adaptive_calls) == 1
    assert chains.plan_calls == []
    assert chains.synthesis_calls == []
    assert searcher.calls == []


def test_provider_timeout_is_a_stable_503_without_retry() -> None:
    chains = FakeChains(
        adaptive=[ModelOutputError("timeout", "provider timed out", stage="adaptive_question")]
    )
    searcher = FakeSearcher()

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.adaptive_calls) == 1
    assert chains.plan_calls == []
    assert chains.synthesis_calls == []
    assert searcher.calls == []


def test_search_failure_is_a_stable_503_without_synthesis_or_retry() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher(error=TimeoutError("search provider timed out"))

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.plan_calls) == 1
    assert len(searcher.calls) == 1
    assert chains.synthesis_calls == []


def test_no_evidence_is_a_stable_503_without_synthesis_or_retry() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher(results=[])

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.plan_calls) == 1
    assert len(searcher.calls) == 1
    assert chains.synthesis_calls == []


def test_no_search_results_is_a_stable_503_without_synthesis() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher(
        error=ModelOutputError("no_search_results", stage="approved_source_search")
    )

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.plan_calls) == 1
    assert len(searcher.calls) == 1
    assert chains.synthesis_calls == []


def test_malformed_synthesis_output_is_a_stable_503() -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[{"what_you_reported": []}],
    )
    searcher = FakeSearcher()

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.synthesis_calls) == 1


def test_ungrounded_synthesis_is_a_stable_503() -> None:
    chains = FakeChains(
        adaptive=[AdaptiveDecision(kind="ready_for_search")],
        assessments=[assessment_draft("S99")],
    )
    searcher = FakeSearcher()

    response = _client(chains, searcher).post("/v1/chat", json=_ready_request())

    _assert_service_error(response)
    assert len(chains.synthesis_calls) == 1


def test_unexpected_application_exception_is_a_safe_500(monkeypatch: Any) -> None:
    def fail_unexpectedly(turn: Any, chains: Any, searcher: Any) -> Any:
        raise RuntimeError("raw provider diagnostics must stay server-side")

    monkeypatch.setattr(app_module, "run_turn", fail_unexpectedly)

    response = _client(FakeChains(), FakeSearcher()).post(
        "/v1/chat", json=_request()
    )

    _assert_service_error(response, status_code=500)
    assert "raw provider diagnostics" not in response.text
