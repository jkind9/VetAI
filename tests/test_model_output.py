"""What happens when the model's answer, or the caller's history, is not usable.

Cases C4 and C6 from documentation/test-cases.md. The API layer that maps these to HTTP 503 and
422 does not exist yet; these pin the two error types it will map, so the split is already
decided when that layer arrives.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.schemas import (
    MAX_REPLY_CHARS,
    InvalidTurnRequest,
    Message,
    ModelOutputError,
    ModelReply,
    TurnRequest,
)
from backend.workflow import SUMMARY_SUFFIX, run_turn
from conftest import FakeChatModel, history, intake


class _SomeOtherShape(BaseModel):
    """What a provider returning a different structured schema would hand back."""

    text: str


def _turn(*messages: Message) -> TurnRequest:
    return TurnRequest(intake=intake(), history=list(messages))


@pytest.mark.parametrize(
    ("bad_reply", "why"),
    [
        ("Just some prose, no structure at all.", "a plain string is not a structured result"),
        ({"kind": "question"}, "missing reply text"),
        ({"reply": "Text with no kind."}, "missing kind"),
        ({"kind": "emergency_notice", "reply": "Go to a vet."}, "the model cannot pick that route"),
        ({"kind": "question", "reply": ""}, "an empty reply is not a reply"),
        ({"kind": "question", "reply": "   "}, "whitespace only"),
        ({"kind": "question", "reply": "x" * (MAX_REPLY_CHARS + 1)}, "over the length cap"),
        (None, "nothing at all"),
        (_SomeOtherShape(text="hi"), "a structured object of the wrong shape is still unusable"),
    ],
)
def test_unusable_model_output_is_a_parse_failure(bad_reply: object, why: str) -> None:
    model = FakeChatModel(bad_reply)

    with pytest.raises(ModelOutputError) as raised:
        run_turn(_turn(), model)

    assert raised.value.parse_failure is True, why
    assert raised.value.reason == "invalid_model_output"


def test_a_model_that_raises_is_reported_without_a_reply() -> None:
    class BrokenModel:
        def propose(self, turn, mode):
            raise RuntimeError("the library fell over")

    with pytest.raises(ModelOutputError) as raised:
        run_turn(_turn(), BrokenModel())

    assert raised.value.parse_failure is False
    assert raised.value.reason == "model_call_failed"


@pytest.mark.parametrize(
    ("bad_history", "why"),
    [
        (history(("Q1", "A1"), ("Q2", "A2")) + [Message(role="assistant", content="Q3")],
         "five messages is over the cap"),
        ([Message(role="assistant", content="Q1")], "no owner answer yet"),
        ([Message(role="user", content="A1"), Message(role="assistant", content="Q1")],
         "roles in the wrong order"),
    ],
)
def test_malformed_history_is_rejected_not_truncated(bad_history, why: str) -> None:
    """Truncating instead would change the prior-question count, which is the question cap."""
    model = FakeChatModel(ModelReply(kind="question", reply="Anything else?"))

    with pytest.raises(InvalidTurnRequest):
        run_turn(TurnRequest(intake=intake(), history=bad_history), model)

    assert model.calls == [], why


def test_an_over_long_history_message_is_rejected_at_the_type() -> None:
    with pytest.raises(ValueError):
        Message(role="user", content="x" * 1001)


def test_a_first_turn_asks_in_ordinary_mode() -> None:
    """The zero-prior-question end of the cap boundary."""
    model = FakeChatModel(ModelReply(kind="question", reply="When did it start?"))

    result = run_turn(_turn(), model)

    assert result.kind == "question"
    assert model.modes[0] == "ordinary"


def test_the_fixed_suffix_is_appended_once_and_only_to_a_recap() -> None:
    model = FakeChatModel(ModelReply(kind="summary", reply="You reported an ear concern."))

    result = run_turn(_turn(), model)

    assert result.reply.count(SUMMARY_SUFFIX) == 1
    assert result.reply.startswith("You reported an ear concern.")

    asking = FakeChatModel(ModelReply(kind="question", reply="When did it start?"))
    assert SUMMARY_SUFFIX not in run_turn(_turn(), asking).reply
