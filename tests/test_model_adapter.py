"""Model-family adapter behaviour that does not require a live Ollama server."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.runnables import RunnableLambda

from backend.model import OllamaChatModel, PromptFile, _parse_function_calling_result
from backend.schemas import AdaptiveDecision, AssessmentDraft
from backend.settings import BackendSettings


def test_model_factory_carries_every_runtime_setting(monkeypatch) -> None:
    constructed: dict[str, Any] = {}

    def record_init(self, model: str, **kwargs: Any) -> None:
        constructed["model"] = model
        constructed["kwargs"] = kwargs

    monkeypatch.setattr(OllamaChatModel, "__init__", record_init)
    settings = BackendSettings(
        model="gpt-oss:20b",
        base_url="http://ollama:11434",
        timeout_seconds=25,
    )

    result = OllamaChatModel.from_settings(settings)

    assert isinstance(result, OllamaChatModel)
    assert constructed == {
        "model": "gpt-oss:20b",
        "kwargs": {
            "base_url": "http://ollama:11434/",
            "timeout": 25.0,
            "structured_output_method": "function_calling",
            "reasoning": "low",
        },
    }


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


def test_function_calling_parser_recovers_known_grounded_item_field_names() -> None:
    result = {
        "raw": SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "args": {
                        "outcome": "possible_problem",
                        "possible_areas": [
                            {"area": "Ear irritation", "source_ids": ["S1"]}
                        ],
                        "suggested_actions": [
                            {"action": "Record visible changes.", "source_ids": ["S1"]}
                        ],
                        "questions_for_veterinarian": [
                            {
                                "question": "What changes should I monitor?",
                                "source_ids": ["S1"],
                            }
                        ],
                    }
                }
            ],
        ),
        "parsed": None,
        "parsing_error": ValueError("nested field names did not match the schema"),
    }

    parsed = _parse_function_calling_result(result, AssessmentDraft)

    assert parsed.possible_areas[0].text == "Ear irritation"
    assert parsed.suggested_actions[0].text == "Record visible changes."
    assert (
        parsed.questions_for_veterinarian[0].text
        == "What changes should I monitor?"
    )
