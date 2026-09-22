"""The rules for one turn of the pet-concern question flow.

`run_turn` is the whole policy, top to bottom: reject malformed history, return the fixed
emergency notice if a curated warning phrase appears in the owner's own words, otherwise make
exactly one model call and check what comes back. Every decision about *what happens* is here.
`model.py` only knows how to phrase a request to a provider; `safeguards.py` only knows which
phrases are warning signs.

Nothing in this module writes clinical content. The two fixed strings below and the model's own
text are all the owner ever sees.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.safeguards import find_emergency
from backend.schemas import (
    MAX_FOLLOW_UP_QUESTIONS,
    MAX_HISTORY_MESSAGES,
    InvalidTurnRequest,
    Message,
    Mode,
    ModelOutputError,
    ModelReply,
    Role,
    TurnRequest,
    TurnResult,
)

# The workflow supplies this wording, never the model. Both are quoted word for word in
# documentation/test-cases.md and asserted by the tests, so they have exactly one definition.

EMERGENCY_NOTICE = (
    "This may be an emergency. Please contact an emergency veterinarian now. "
    "This demo cannot assess your pet or provide a diagnosis."
)

SUMMARY_SUFFIX = (
    "This is not a diagnosis. Please discuss your pet's concern with a veterinarian."
)


def run_turn(turn: TurnRequest, model: Any) -> TurnResult:
    """Produce the reply for one turn.

    `model` is anything with a `propose(turn, mode)` method: `OllamaChatModel` in `model.py`,
    or the stand-in in the tests. This module imports nothing from `model.py`, so neither
    the workflow nor its tests ever load LangChain.

    Raises `InvalidTurnRequest` if the caller's history is malformed, or `ModelOutputError` if
    the model call fails or its answer is unusable. It never substitutes text of its own for a
    failed call.
    """
    _validate_history(turn.history)

    emergency = find_emergency(_owner_written_text(turn))
    if emergency is not None:
        # Fixed wording and no model call, so nothing can soften or reword an escalation.
        return TurnResult(
            kind="emergency_notice", reply=EMERGENCY_NOTICE, emergency_rule=emergency.rule
        )

    questions_already_asked = sum(1 for message in turn.history if message.role == "assistant")
    may_ask_another = questions_already_asked < MAX_FOLLOW_UP_QUESTIONS
    mode: Mode = "ordinary" if may_ask_another else "summary_only"

    reply = _ask_model(model, turn, mode)

    if reply.kind == "question" and not may_ask_another:
        # The prompt asks for a recap in this mode, but the cap is enforced here so it does not
        # depend on the model co-operating.
        raise ModelOutputError(
            "question_limit_violation",
            f"the model asked another question after {MAX_FOLLOW_UP_QUESTIONS} already",
        )

    if reply.kind == "summary":
        return TurnResult(kind="summary", reply=f"{reply.reply}\n\n{SUMMARY_SUFFIX}")
    return TurnResult(kind="question", reply=reply.reply)


def _validate_history(history: list[Message]) -> None:
    """Accept zero, one, or two complete question-and-answer pairs, and nothing else.

    Malformed history is rejected rather than trimmed, because the number of assistant messages
    in it *is* the follow-up count that `run_turn` caps. A summary or emergency notice ends the
    chat and is never sent back, so neither appears here.
    """
    if len(history) > MAX_HISTORY_MESSAGES:
        raise InvalidTurnRequest(
            f"chat history holds at most {MAX_HISTORY_MESSAGES} messages, got {len(history)}"
        )
    if len(history) % 2 != 0:
        raise InvalidTurnRequest(
            "chat history must end with the owner's answer to the last question"
        )
    for index, message in enumerate(history):
        expected: Role = "assistant" if index % 2 == 0 else "user"
        if message.role != expected:
            raise InvalidTurnRequest(
                f"chat history message {index} should be from the {expected}, "
                f"got {message.role!r}"
            )


def _owner_written_text(turn: TurnRequest) -> list[str]:
    """Everything in this chat the owner wrote: the concern, the duration box, every answer.

    All of it is re-read on every turn, so a warning sign reported earlier still counts later.
    Assistant questions are left out on purpose: "Is she struggling to breathe?" is the demo's own
    wording, and answering "No" to it must not escalate the chat.
    """
    texts = [turn.intake.concern]
    if turn.intake.duration != "unknown":
        texts.append(turn.intake.duration)
    texts.extend(message.content for message in turn.history if message.role == "user")
    return texts


def _ask_model(model: Any, turn: TurnRequest, mode: Mode) -> ModelReply:
    """Make the single model call for this turn and return an answer that fits `ModelReply`.

    One turn, one call: there is no retry, and no fallback text. Anything a provider raises
    becomes a `ModelOutputError` so callers never see a LangChain or HTTP exception. Structure is
    all that is checked here — whether a reply is relevant, factual, or medically sensible is a
    prompt and human-review question, not something this code can decide.
    """
    try:
        raw = model.propose(turn, mode)
    except ModelOutputError:
        raise  # the adapter recognised its own failure (timeout, connection) and said so
    except Exception as error:  # noqa: BLE001 - re-raised below, never swallowed
        raise ModelOutputError("model_call_failed", type(error).__name__) from error

    try:
        return ModelReply.model_validate(raw)
    except ValidationError as error:
        raise ModelOutputError(
            "invalid_model_output",
            str(error.errors(include_url=False, include_input=False)),
        ) from error
