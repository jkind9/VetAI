"""Four explicit LangChain/Ollama stages for safety, questions, query, and synthesis."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.schemas import (
    AdaptiveDecision,
    AssessmentDraft,
    EmergencyCheck,
    EvidenceItem,
    FailureReason,
    ModelOutputError,
    QuestionMode,
    SearchPlan,
    TurnRequest,
)

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"
EMERGENCY_PROMPT_PATH = PROMPT_ROOT / "emergency_check.md"
ADAPTIVE_PROMPT_PATH = PROMPT_ROOT / "adaptive_question.md"
SEARCH_PROMPT_PATH = PROMPT_ROOT / "search_queries.md"
SYNTHESIS_PROMPT_PATH = PROMPT_ROOT / "evidence_synthesis.md"
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 60.0
SYSTEM_MARKER = "<!-- system -->"
HUMAN_MARKER = "<!-- human -->"

MODE_INSTRUCTIONS: dict[QuestionMode, str] = {
    "question_required": (
        "Return `question` and ask exactly one useful question. This is the first adaptive turn, "
        "so `ready_for_search` is not allowed."
    ),
    "question_or_ready": (
        "Return one useful question if an important descriptive detail is still missing, or "
        "`ready_for_search` with question set to null."
    ),
}


@dataclass(frozen=True)
class PromptFile:
    path: Path
    system: str
    human: str
    sha256: str

    @classmethod
    def load(cls, path: Path | str) -> PromptFile:
        resolved = Path(path)
        text = resolved.read_text(encoding="utf-8")
        if SYSTEM_MARKER not in text or HUMAN_MARKER not in text:
            raise ValueError(
                f"{resolved} must contain both {SYSTEM_MARKER} and {HUMAN_MARKER} markers"
            )
        _, after_system = text.split(SYSTEM_MARKER, 1)
        system, human = after_system.split(HUMAN_MARKER, 1)
        return cls(
            path=resolved,
            system=system.strip(),
            human=human.strip(),
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )


class OllamaChatModel:
    """Share one local model across four separately inspectable LangChain pipelines."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.0,
        seed: int = 42,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        emergency_prompt: PromptFile | None = None,
        adaptive_prompt: PromptFile | None = None,
        search_prompt: PromptFile | None = None,
        synthesis_prompt: PromptFile | None = None,
        structured_output_method: str = "json_schema",
    ) -> None:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama

        self.model = model
        self.emergency_prompt = emergency_prompt or PromptFile.load(EMERGENCY_PROMPT_PATH)
        self.adaptive_prompt = adaptive_prompt or PromptFile.load(ADAPTIVE_PROMPT_PATH)
        self.search_prompt = search_prompt or PromptFile.load(SEARCH_PROMPT_PATH)
        self.synthesis_prompt = synthesis_prompt or PromptFile.load(SYNTHESIS_PROMPT_PATH)
        self.structured_output_method = structured_output_method
        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            seed=seed,
            num_predict=900,
            client_kwargs={"timeout": timeout},
        )
        self._emergency_chain = self._make_chain(
            ChatPromptTemplate, llm, self.emergency_prompt, EmergencyCheck
        )
        self._adaptive_chain = self._make_chain(
            ChatPromptTemplate, llm, self.adaptive_prompt, AdaptiveDecision
        )
        self._search_chain = self._make_chain(
            ChatPromptTemplate, llm, self.search_prompt, SearchPlan
        )
        self._synthesis_chain = self._make_chain(
            ChatPromptTemplate, llm, self.synthesis_prompt, AssessmentDraft
        )

    def _make_chain(self, template_type: Any, llm: Any, prompt: PromptFile, schema: Any) -> Any:
        from langchain_core.runnables import RunnableLambda

        template = template_type.from_messages(
            [("system", prompt.system), ("human", prompt.human)]
        )
        if self.structured_output_method == "function_calling":
            structured_llm = llm.with_structured_output(
                schema, method=self.structured_output_method, include_raw=True
            )
            parse_result = RunnableLambda(
                lambda result: _parse_function_calling_result(result, schema)
            )
            return template | structured_llm | parse_result
        return template | llm.with_structured_output(
            schema, method=self.structured_output_method
        )

    @property
    def prompt_hashes(self) -> dict[str, str]:
        return {
            "emergency_check": self.emergency_prompt.sha256,
            "adaptive_question": self.adaptive_prompt.sha256,
            "search_query": self.search_prompt.sha256,
            "evidence_synthesis": self.synthesis_prompt.sha256,
        }

    def check_for_emergency(self, turn: TurnRequest) -> EmergencyCheck:
        return self._invoke(self._emergency_chain, _turn_variables(turn), "emergency_check")

    def propose_adaptive_question(
        self, turn: TurnRequest, mode: QuestionMode
    ) -> AdaptiveDecision:
        variables = _turn_variables(turn) | {"mode_instruction": MODE_INSTRUCTIONS[mode]}
        return self._invoke(self._adaptive_chain, variables, "adaptive_question")

    def generate_search_plan(self, turn: TurnRequest) -> SearchPlan:
        return self._invoke(self._search_chain, _turn_variables(turn), "search_query")

    def synthesise_assessment(
        self, turn: TurnRequest, evidence: list[EvidenceItem]
    ) -> AssessmentDraft:
        variables = _turn_variables(turn) | {
            "evidence": json.dumps(
                [item.model_dump(mode="json") for item in evidence],
                ensure_ascii=False,
                indent=2,
            )
        }
        return self._invoke(self._synthesis_chain, variables, "evidence_synthesis")

    @staticmethod
    def _invoke(chain: Any, variables: dict[str, str], stage: str) -> Any:
        try:
            return chain.invoke(variables)
        except ModelOutputError:
            raise
        except Exception as error:  # provider diagnostics never cross this boundary
            raise ModelOutputError(
                _failure_reason(error), type(error).__name__, stage=stage
            ) from error


def _parse_function_calling_result(result: dict[str, Any], schema: Any) -> Any:
    """Validate gpt-oss output whether Ollama used a tool call or JSON message content."""
    if result.get("parsed") is not None:
        return result["parsed"]
    content = getattr(result.get("raw"), "content", None)
    if not isinstance(content, str):
        return None
    return schema.model_validate_json(content)


def _turn_variables(turn: TurnRequest) -> dict[str, str]:
    if turn.history:
        speaker = {"assistant": "VetAI asked", "user": "Owner answered"}
        transcript = "\n".join(
            f"{speaker[message.role]}: {message.content}" for message in turn.history
        )
    else:
        transcript = "(no questions answered yet)"
    return {
        "species": turn.intake.species,
        "concern": turn.intake.concern,
        "transcript": transcript,
    }


def _failure_reason(error: Exception) -> FailureReason:
    name = f"{type(error).__module__}.{type(error).__name__}".lower()
    if any(word in name for word in ("outputparser", "jsondecode", "validation")):
        return "invalid_model_output"
    if "timeout" in name:
        return "timeout"
    if any(word in name for word in ("connect", "refused", "unreachable")):
        return "connection"
    return "model_call_failed"
