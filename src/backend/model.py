"""How the backend talks to a local model: the prompt file, the interface, and the Ollama adapter.

No policy lives here. `workflow.py` has already decided that a model should be called and which
mode it may answer in; this module turns that into a prompt, makes one call, and hands back
whatever the provider returned for the workflow to validate. It never inspects the answer, and it
never produces text of its own.

Everything configurable is a constructor argument. This module reads no environment variable and
no config file, so a later settings layer can supply those values without changing it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.schemas import (
    MAX_REPLY_CHARS,
    FailureReason,
    Mode,
    ModelOutputError,
    ModelReply,
    TurnRequest,
)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "question_flow.md"
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 60.0

SYSTEM_MARKER = "<!-- system -->"
HUMAN_MARKER = "<!-- human -->"

# The one line of the prompt that differs between the two modes. `summary_only` means the
# workflow has already spent the follow-up cap; it will reject a question whatever this says.
MODE_INSTRUCTIONS: dict[Mode, str] = {
    "ordinary": (
        "Choose one of two things. Either ask the single most useful follow-up question, with "
        "`kind` set to `question`, or, if you already have enough to be useful, write the recap "
        "with `kind` set to `summary`. Prefer the recap when another question would add little."
    ),
    "summary_only": (
        "The owner has already answered two follow-up questions. Write the recap now, with "
        "`kind` set to `summary`. Do not ask anything further."
    ),
}


@dataclass(frozen=True)
class PromptFile:
    """The versioned prompt, split into its two sections and hashed whole.

    `sha256` covers the entire file, including the notes above the markers, so any edit to the
    prompt is visible as a different hash to a later tracking layer.
    """

    path: Path
    system: str
    human: str
    sha256: str

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PROMPT_PATH) -> PromptFile:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if SYSTEM_MARKER not in text or HUMAN_MARKER not in text:
            raise ValueError(
                f"{path} must contain both {SYSTEM_MARKER} and {HUMAN_MARKER} markers"
            )
        _, after_system = text.split(SYSTEM_MARKER, 1)
        system, human = after_system.split(HUMAN_MARKER, 1)
        return cls(
            path=path,
            system=system.strip(),
            human=human.strip(),
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )


class OllamaChatModel:
    """Call a local Ollama model through LangChain and ask for a structured answer.

    `with_structured_output` requests the `ModelReply` schema. That is a request, not a guarantee,
    which is why the workflow validates the result again.
    """

    def __init__(
        self,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.0,
        seed: int = 42,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        prompt: PromptFile | None = None,
        structured_output_method: str = "json_schema",
    ) -> None:
        # Imported here, not at module level, so the workflow and its tests never load LangChain.
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama

        self.model = model
        self.prompt = prompt or PromptFile.load()
        self.structured_output_method = structured_output_method
        self._llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            seed=seed,
            # Room for the longest allowed reply plus its JSON wrapper, at roughly three
            # characters per token.
            num_predict=MAX_REPLY_CHARS // 3 + 64,
            client_kwargs={"timeout": timeout},
        )
        template = ChatPromptTemplate.from_messages(
            [("system", self.prompt.system), ("human", self.prompt.human)]
        )
        self._chain = template | self._llm.with_structured_output(
            ModelReply, method=structured_output_method
        )

    def propose(self, turn: TurnRequest, mode: Mode) -> Any:
        try:
            return self._chain.invoke(_prompt_variables(turn, mode))
        except Exception as error:  # noqa: BLE001 - named and re-raised, never swallowed
            raise ModelOutputError(_failure_reason(error), type(error).__name__) from error


def _prompt_variables(turn: TurnRequest, mode: Mode) -> dict[str, str]:
    """Fill the placeholders in prompts/question_flow.md."""
    if turn.history:
        speaker = {"assistant": "You asked", "user": "Owner answered"}
        transcript = "\n".join(
            f"{speaker[m.role]}: {m.content}" for m in turn.history
        )
    else:
        transcript = "(nothing yet — this is the first message)"

    intake = turn.intake
    return {
        "mode_instruction": MODE_INSTRUCTIONS[mode],
        "species": intake.species,
        "concern": intake.concern,
        "duration": intake.duration,
        "previous_occurrence": intake.previous_occurrence,
        "pattern": intake.pattern,
        "transcript": transcript,
    }


def _failure_reason(error: Exception) -> FailureReason:
    """Name the failure from the exception's type, without importing client-specific classes.

    A timeout and an unreachable Ollama are worth telling apart in tracking; anything else is
    reported as a plain call failure rather than guessed at.
    """
    name = f"{type(error).__module__}.{type(error).__name__}".lower()
    if "timeout" in name:
        return "timeout"
    if any(word in name for word in ("connect", "refused", "unreachable")):
        return "connection"
    return "model_call_failed"
