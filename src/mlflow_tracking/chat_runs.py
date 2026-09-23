"""Record each chat turn in MLflow.

Every turn is one MLflow run. The run holds the turn's parameters, how long it took, and what kind
of reply it gave. Inside the run, one trace holds every LangChain call the turn made: the exact
prompt sent, the model's reply, and the time each step took.

MLflow writes to MLFLOW_TRACKING_URI when it is set, and otherwise to ./mlflow.db.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import mlflow
from mlflow.environment_variables import MLFLOW_ENABLE_ASYNC_TRACE_LOGGING

from backend.schemas import ModelOutputError, TurnRequest, TurnResult
from backend.workflow import run_turn

EXPERIMENT_NAME = "vetai-chat"


def start_tracking() -> None:
    """Record runs in the VetAI experiment, and trace every LangChain call from now on."""
    # Save each trace into the database before its turn returns. With background saving, MLflow
    # sometimes writes a trace to files under ./mlruns instead, which splits the data in two and
    # fails in the Docker image, where /app is not writable. Must run before the first trace.
    MLFLOW_ENABLE_ASYNC_TRACE_LOGGING.set(False)
    mlflow.set_experiment(EXPERIMENT_NAME)
    mlflow.langchain.autolog()


def run_tracked_turn(
    turn: TurnRequest, chains: Any, searcher: Any, run_params: dict[str, str]
) -> tuple[TurnResult, str]:
    """Run one chat turn as its own MLflow run. Return the result and the run's id.

    `run_params` are recorded as they are, for example the model name. A turn that fails with
    `ModelOutputError` is marked FAILED with the stage that failed, and the error is re-raised.
    """
    with mlflow.start_run(run_name="chat_turn") as run:
        mlflow.log_params(
            run_params
            | {"species": turn.intake.species, "answered_questions": len(turn.history) // 2}
        )
        started = perf_counter()
        try:
            # run_id ties this trace to this run. Without it, MLflow links a new trace to the
            # latest open run in any thread, which is the wrong run when two turns overlap.
            with mlflow.start_span(name="chat_turn", run_id=run.info.run_id) as span:
                span.set_inputs(turn.model_dump(mode="json"))
                result = run_turn(turn, chains, searcher)
                span.set_outputs(result.model_dump(mode="json"))
        except ModelOutputError as error:
            mlflow.set_tags({"failed_stage": error.stage, "failure_reason": error.reason})
            raise
        finally:
            mlflow.log_metric("turn_seconds", perf_counter() - started)
        mlflow.set_tag("reply_kind", result.kind)
    return result, run.info.run_id
