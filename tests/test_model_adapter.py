"""Model-family adapter behaviour that does not require a live Ollama server."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.runnables import RunnableLambda

from backend.model import OllamaChatModel, PromptFile
from backend.schemas import AdaptiveDecision


def test_function_calling_chain_accepts_schema_json_when_model_ignores_tool() -> None:
    options: dict[str, Any] = {}

    class PassthroughTemplate:
        @classmethod
        def from_messages(cls, messages: object) -> RunnableLambda:
            return RunnableLambda(lambda variables: variables)

    class JsonContentModel:
        def with_structured_output(
            self, schema: object, *, method: str, include_raw: bool = False
        ) -> RunnableLambda:
            options.update(method=method, include_raw=include_raw)
            if not include_raw:
                return RunnableLambda(lambda _: None)
            return RunnableLambda(
                lambda _: {
                    "raw": SimpleNamespace(
                        content=(
                            '{"kind":"question","question":'
                            '"Do you notice any coughing or wheezing?"}'
                        )
                    ),
                    "parsed": None,
                    "parsing_error": None,
                }
            )

    model = object.__new__(OllamaChatModel)
    model.structured_output_method = "function_calling"
    prompt = PromptFile(Path("test.md"), "System", "Human", "prompt-hash")

    result = model._make_chain(
        PassthroughTemplate, JsonContentModel(), prompt, AdaptiveDecision
    ).invoke({})

    assert options == {"method": "function_calling", "include_raw": True}
    assert result == AdaptiveDecision(
        kind="question", question="Do you notice any coughing or wheezing?"
    )
