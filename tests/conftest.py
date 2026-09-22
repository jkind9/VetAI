"""Shared test helpers.

The stand-in model here is why an ordinary test run needs neither Ollama nor a network. It
returns whatever it was given — including a deliberately malformed value — and records each call,
so a test can assert both whether the model was asked at all and which mode it was asked for.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import Intake, Message, Mode, ModelReply, TurnRequest


class FakeChatModel:
    """Returns one fixed answer, and remembers what it was asked.

    `calls` holds the turns it was given and `modes` the mode of each, so a test can assert
    both that the model was (or was not) asked and which mode the workflow chose.
    """

    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.calls: list[TurnRequest] = []
        self.modes: list[Mode] = []

    def propose(self, turn: TurnRequest, mode: Mode) -> Any:
        self.calls.append(turn)
        self.modes.append(mode)
        return self.reply


def question(text: str = "When did you first notice it?") -> ModelReply:
    return ModelReply(kind="question", reply=text)


def summary(text: str = "You reported that your dog scratched one ear today.") -> ModelReply:
    return ModelReply(kind="summary", reply=text)


def intake(concern: str = "My dog scratched one ear today.", **overrides: Any) -> Intake:
    """Default intake from documentation/test-cases.md: dog, everything else unknown."""
    fields: dict[str, Any] = {
        "species": "dog",
        "concern": concern,
        "duration": "unknown",
        "previous_occurrence": "unknown",
        "pattern": "unknown",
    }
    fields.update(overrides)
    return Intake(**fields)


def history(*pairs: tuple[str, str]) -> list[Message]:
    """Build an alternating assistant-question / owner-answer history."""
    messages: list[Message] = []
    for asked, answered in pairs:
        messages.append(Message(role="assistant", content=asked))
        messages.append(Message(role="user", content=answered))
    return messages

