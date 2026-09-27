"""Each chat turn is one MLflow run, with the turn's LangChain calls traced inside it.

The runs go to the throwaway database that conftest.py points MLflow at.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import mlflow
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.prompts import ChatPromptTemplate
from mlflow import MlflowClient
from mlflow.entities import Run, Trace
from mlflow.exceptions import MlflowException

import mlflow_tracking.chat_runs as chat_runs
from backend.app import create_app
from backend.error_handling import SERVICE_ERROR_TEXT
from backend.schemas import (
    AdaptiveDecision,
    EmergencyCheck,
    ModelOutputError,
    QuestionMode,
    TurnRequest,
)
from conftest import FakeChains, FakeSearcher, standard_history
from mlflow_tracking.chat_runs import EXPERIMENT_NAME, start_tracking

QUESTION_CHAIN = ChatPromptTemplate.from_messages(
    [("human", "Ask one question about: {concern}")]
) | FakeListChatModel(responses=["What else have you noticed?"])
EMERGENCY_CHAIN = ChatPromptTemplate.from_messages(
    [("human", "Check for an emergency in: {concern}")]
) | FakeListChatModel(responses=["No emergency"])


class QuestionFromLangChain:
    """Stand-in whose emergency and adaptive steps make real traceable LangChain calls."""

    def check_for_emergency(self, turn: TurnRequest) -> EmergencyCheck:
        EMERGENCY_CHAIN.invoke({"concern": turn.intake.concern})
        return EmergencyCheck(emergency=False)

    def propose_adaptive_question(
        self, turn: TurnRequest, mode: QuestionMode
    ) -> AdaptiveDecision:
        reply = QUESTION_CHAIN.invoke({"concern": turn.intake.concern})
        return AdaptiveDecision(kind="question", question=reply.content)


def test_default_tracking_uri_stays_relative_when_environment_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured: list[str] = []
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr(chat_runs.mlflow, "set_tracking_uri", configured.append)
    monkeypatch.setattr(
        chat_runs,
        "MlflowClient",
        lambda: SimpleNamespace(get_experiment_by_name=lambda _: None),
    )
    monkeypatch.setattr(chat_runs.mlflow, "set_experiment", lambda _: None)
    monkeypatch.setattr(chat_runs.mlflow.langchain, "autolog", lambda: None)

    start_tracking()

    assert configured == ["sqlite:///mlflow.db"]


def test_explicit_tracking_uri_is_not_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    configured: list[str] = []
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///configured.db")
    monkeypatch.setattr(chat_runs.mlflow, "set_tracking_uri", configured.append)
    monkeypatch.setattr(
        chat_runs,
        "MlflowClient",
        lambda: SimpleNamespace(get_experiment_by_name=lambda _: None),
    )
    monkeypatch.setattr(chat_runs.mlflow, "set_experiment", lambda _: None)
    monkeypatch.setattr(chat_runs.mlflow.langchain, "autolog", lambda: None)

    start_tracking()

    assert configured == []


def _request(
    concern: str = "My dog keeps scratching", *, after_standard_questions: bool = False
) -> dict[str, Any]:
    """A turn request; every unmatched turn calls the emergency model first."""
    history = standard_history() if after_standard_questions else []
    return {
        "intake": {"species": "dog", "concern": concern},
        "history": [message.model_dump() for message in history],
    }


def _newest_run() -> Run:
    return mlflow.search_runs(
        search_all_experiments=True,
        order_by=["attributes.start_time DESC"],
        max_results=1,
        output_format="list",
    )[0]


def _traces_of(run_id: str) -> list[Trace]:
    experiment_id = mlflow.get_run(run_id).info.experiment_id
    return mlflow.search_traces(locations=[experiment_id], run_id=run_id, return_type="list")


def _root_span(trace: Trace) -> Any:
    return next(span for span in trace.data.spans if span.parent_id is None)


def _delete_the_experiment() -> None:
    """What the MLflow UI's Delete button does: move the experiment to MLflow's bin."""
    client = MlflowClient()
    client.delete_experiment(client.get_experiment_by_name(EXPERIMENT_NAME).experiment_id)


@pytest.fixture
def restore_the_experiment_afterwards():
    """Later tests need the experiment, so bring it back even if a test fails."""
    yield
    client = MlflowClient()
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment.lifecycle_stage == "deleted":
        client.restore_experiment(experiment.experiment_id)
    mlflow.set_experiment(EXPERIMENT_NAME)


def test_each_turn_is_one_finished_run() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher(), {"model": "stand-in"}))

    run_id = client.post("/v1/chat", json=_request()).json()["run_id"]

    run = mlflow.get_run(run_id)
    assert run.info.status == "FINISHED"
    assert run.data.params == {"model": "stand-in", "species": "dog", "answered_questions": "0"}
    assert run.data.tags["reply_kind"] == "question"
    assert run.data.metrics["turn_seconds"] >= 0


def test_turn_without_run_params_is_still_tracked() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher()))

    run_id = client.post("/v1/chat", json=_request()).json()["run_id"]

    assert mlflow.get_run(run_id).data.params == {"species": "dog", "answered_questions": "0"}


def test_failed_turn_is_marked_failed_with_its_stage() -> None:
    chains = FakeChains(adaptive=[ModelOutputError("timeout", stage="adaptive_question")])
    client = TestClient(create_app(chains, FakeSearcher()), raise_server_exceptions=False)

    response = client.post("/v1/chat", json=_request(after_standard_questions=True))

    assert response.status_code == 503
    assert response.json() == {"error": SERVICE_ERROR_TEXT, "run_id": None}
    run = _newest_run()
    assert run.info.status == "FAILED"
    assert run.data.tags["failed_stage"] == "adaptive_question"
    assert run.data.tags["failure_reason"] == "timeout"
    assert "turn_seconds" in run.data.metrics


def test_turn_trace_holds_prompt_reply_and_time() -> None:
    start_tracking()
    client = TestClient(create_app(QuestionFromLangChain(), FakeSearcher()))

    request = _request("My dog keeps scratching", after_standard_questions=True)
    run_id = client.post("/v1/chat", json=request).json()["run_id"]

    traces = _traces_of(run_id)
    assert len(traces) == 1
    root = _root_span(traces[0])
    chat_models = [span for span in traces[0].data.spans if span.span_type == "CHAT_MODEL"]
    assert root.name == "chat_turn"
    assert root.inputs["intake"]["concern"] == "My dog keeps scratching"
    assert len(chat_models) == 2
    model_inputs = " ".join(str(span.inputs) for span in chat_models)
    model_outputs = " ".join(str(span.outputs) for span in chat_models)
    assert "Check for an emergency in: My dog keeps scratching" in model_inputs
    assert "Ask one question about: My dog keeps scratching" in model_inputs
    assert "No emergency" in model_outputs
    assert "What else have you noticed?" in model_outputs
    assert traces[0].info.execution_duration is not None


def test_overlapping_turns_keep_their_own_traces(monkeypatch: pytest.MonkeyPatch) -> None:
    start_tracking()
    # Hold both turns after their runs start and before their traces start. With two runs open,
    # MLflow's default linking would attach both traces to the same run.
    both_runs_open = threading.Barrier(2, timeout=10)
    log_params = mlflow.log_params

    def log_params_then_wait(params: dict[str, Any]) -> None:
        log_params(params)
        both_runs_open.wait()

    monkeypatch.setattr(mlflow, "log_params", log_params_then_wait)
    client = TestClient(create_app(QuestionFromLangChain(), FakeSearcher()))
    run_ids: dict[str, str] = {}

    def send(concern: str) -> None:
        request = _request(concern, after_standard_questions=True)
        run_ids[concern] = client.post("/v1/chat", json=request).json()["run_id"]

    threads = [
        threading.Thread(target=send, args=(concern,))
        for concern in ("Dog A keeps scratching", "Dog B is limping")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(run_ids) == 2
    for concern, run_id in run_ids.items():
        traces = _traces_of(run_id)
        assert len(traces) == 1
        assert _root_span(traces[0]).inputs["intake"]["concern"] == concern


def test_a_deleted_experiment_is_restored_when_tracking_starts(
    restore_the_experiment_afterwards,
) -> None:
    _delete_the_experiment()

    start_tracking()

    experiment = MlflowClient().get_experiment_by_name(EXPERIMENT_NAME)
    assert experiment.lifecycle_stage == "active"


def test_a_turn_is_still_answered_when_its_run_cannot_be_opened(
    restore_the_experiment_afterwards,
) -> None:
    _delete_the_experiment()
    client = TestClient(create_app(FakeChains(), FakeSearcher()))

    response = client.post("/v1/chat", json=_request("My dog collapsed"))

    assert response.status_code == 200
    assert response.json()["kind"] == "emergency_notice"
    assert response.json()["run_id"] is None


def test_a_rejected_history_is_recorded_with_its_reason() -> None:
    client = TestClient(create_app(FakeChains(), FakeSearcher()))
    request = _request()
    request["history"] = [{"role": "assistant", "content": "How long has this been happening?"}]

    response = client.post("/v1/chat", json=request)

    run = _newest_run()
    assert response.status_code == 422
    assert run.info.status == "FAILED"
    assert run.data.tags["failure_reason"] == "InvalidTurnRequest"


def test_many_turns_at_once_are_all_answered_and_recorded() -> None:
    # 48 model turns at once used to exhaust MLflow's shared pool of 15 database connections:
    # some requests failed after a 30-second wait and some runs lost their trace.
    start_tracking()
    client = TestClient(create_app(QuestionFromLangChain(), FakeSearcher()))
    all_ready = threading.Barrier(48, timeout=10)
    replies: list[dict[str, Any]] = []

    def send(number: int) -> None:
        request = _request(f"Dog {number} is scratching", after_standard_questions=True)
        all_ready.wait()
        replies.append(client.post("/v1/chat", json=request).json())

    threads = [threading.Thread(target=send, args=(number,)) for number in range(48)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert [reply.get("kind") for reply in replies] == ["question"] * 48
    assert all(len(_traces_of(reply["run_id"])) == 1 for reply in replies)


def _fail_with_a_locked_database(*args: Any, **kwargs: Any) -> None:
    raise MlflowException("database is locked")


@pytest.mark.parametrize("write", ["log_params", "set_tag", "log_metric", "end_run"])
def test_a_failed_mlflow_write_does_not_cost_the_reply(
    monkeypatch: pytest.MonkeyPatch, write: str
) -> None:
    monkeypatch.setattr(mlflow, write, _fail_with_a_locked_database)
    client = TestClient(create_app(FakeChains(), FakeSearcher()))

    response = client.post("/v1/chat", json=_request("My dog collapsed"))

    assert response.status_code == 200
    assert response.json()["kind"] == "emergency_notice"


def test_a_rejected_history_keeps_its_422_when_an_mlflow_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mlflow, "log_metric", _fail_with_a_locked_database)
    client = TestClient(create_app(FakeChains(), FakeSearcher()))
    request = _request()
    request["history"] = [{"role": "assistant", "content": "How long has this been happening?"}]

    response = client.post("/v1/chat", json=request)

    assert response.status_code == 422


def test_a_turn_without_a_run_does_not_trace_into_another_turns_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Another turn's run is open. MLflow files a trace that has no run of its own under the
    # newest open run in any thread, so an untraced fallback is the only safe choice.
    client = TestClient(create_app(QuestionFromLangChain(), FakeSearcher()))
    with mlflow.start_run(run_name="another_turn") as other_turn:
        monkeypatch.setattr(mlflow, "start_run", _fail_with_a_locked_database)

        response = client.post("/v1/chat", json=_request(after_standard_questions=True))

    assert response.status_code == 200
    assert response.json()["kind"] == "question"
    assert response.json()["run_id"] is None
    assert _traces_of(other_turn.info.run_id) == []
