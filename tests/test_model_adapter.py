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


def test_model_sets_a_context_window_that_fits_the_largest_prompt(monkeypatch) -> None:
    """Ollama's default window (about 2,048 tokens) silently cut the rules off long prompts."""
    import json

    import langchain_ollama

    from backend import model as model_module
    from backend.schemas import (
        MAX_CONCERN_CHARS,
        MAX_EVIDENCE_CHARS,
        MAX_HISTORY_MESSAGES,
        MAX_MESSAGE_CHARS,
    )
    from backend.search import MAX_EVIDENCE_ITEMS

    constructed: dict[str, Any] = {}

    class RecordingChatOllama:
        def __init__(self, **kwargs: Any) -> None:
            constructed.update(kwargs)

        def with_structured_output(self, *args: Any, **kwargs: Any) -> RunnableLambda:
            return RunnableLambda(lambda _: None)

    monkeypatch.setattr(langchain_ollama, "ChatOllama", RecordingChatOllama)
    OllamaChatModel("gpt-oss:20b")

    prompt = PromptFile.load(model_module.SYNTHESIS_PROMPT_PATH)
    evidence = json.dumps(
        [
            {
                "source_id": f"S{n}",
                "title": "t" * 300,
                "url": "https://www.example.org/" + "p" * 100,
                "organisation": "o" * 60,
                "excerpt": "e" * MAX_EVIDENCE_CHARS,
            }
            for n in range(1, MAX_EVIDENCE_ITEMS + 1)
        ],
        indent=2,
    )
    worst_case_chars = (
        len(prompt.system)
        + len(prompt.human)
        + MAX_CONCERN_CHARS
        + MAX_HISTORY_MESSAGES * (MAX_MESSAGE_CHARS + 20)
        + len(evidence)
    )
    # Real English page text runs about 4 characters per token; 3 leaves a safety margin.
    worst_case_tokens = worst_case_chars // 3

    assert constructed["num_ctx"] >= worst_case_tokens + constructed["num_predict"]
