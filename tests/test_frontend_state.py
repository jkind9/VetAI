"""The desktop keeps drafts local until a request succeeds."""

from __future__ import annotations

from dataclasses import replace

import pytest

from conftest import assessment_payload
from frontend.local.api_client import ApiResult
from frontend.local.app import Bubble, ChatState, accept, reject, request_body, start_chat

FIRST_QUESTION = ApiResult(kind="question", reply="How long has this been happening?")
SECOND_QUESTION = ApiResult(kind="question", reply="Has this happened before?")


def _asked_and_answered(answer: str) -> ChatState:
    """A chat whose first question is on screen with `answer` typed but not yet sent."""
    asked = accept(start_chat("dog", "My dog scratched one ear."), FIRST_QUESTION)
    return replace(asked, draft_answer=answer)


def test_first_request_holds_only_species_concern_and_no_history() -> None:
    state = start_chat("dog", "My dog scratched one ear.")

    assert request_body(state) == {
        "intake": {"species": "dog", "concern": "My dog scratched one ear."},
        "history": [],
    }


def test_concern_is_the_first_owner_bubble() -> None:
    state = start_chat("cat", "She keeps sneezing.")

    assert state.transcript == (Bubble("owner", "She keeps sneezing."),)


def test_question_success_commits_only_the_accepted_pair() -> None:
    state = _asked_and_answered("Yesterday")
    snapshot = request_body(state)

    state = accept(state, SECOND_QUESTION)

    assert snapshot["history"] == [
        {"role": "assistant", "content": FIRST_QUESTION.reply},
        {"role": "user", "content": "Yesterday"},
    ]
    assert list(state.history) == snapshot["history"]
    assert state.current_question == SECOND_QUESTION.reply
    assert state.draft_answer == ""


def test_an_answer_bubble_appears_only_after_success() -> None:
    state = _asked_and_answered("Yesterday")
    before = [(bubble.author, bubble.text) for bubble in state.transcript]

    state = accept(state, SECOND_QUESTION)

    assert before == [("owner", "My dog scratched one ear."), ("vetai", FIRST_QUESTION.reply)]
    assert [(bubble.author, bubble.text) for bubble in state.transcript] == before + [
        ("owner", "Yesterday"),
        ("vetai", SECOND_QUESTION.reply),
    ]


def test_failure_keeps_history_and_draft_and_leaves_the_old_state_alone() -> None:
    sending = replace(_asked_and_answered("Yesterday"), pending=True)

    failed = reject(sending, "The request timed out. Please try again.")

    assert request_body(failed) == request_body(sending)
    assert failed.draft_answer == "Yesterday"
    assert failed.error == "The request timed out. Please try again."
    assert failed.pending is False
    assert sending.pending is True
    assert sending.error is None


@pytest.mark.parametrize(
    "result",
    [
        ApiResult(kind="emergency_notice", reply="Please contact an emergency veterinarian now."),
        ApiResult(kind="assessment", assessment=assessment_payload()),
    ],
)
def test_assessment_or_emergency_notice_ends_the_chat(result: ApiResult) -> None:
    state = accept(_asked_and_answered("Yesterday"), result)

    assert state.ended is True
    assert state.current_question is None
    assert state.transcript[-2] == Bubble("owner", "Yesterday")
    assert state.transcript[-1].kind == result.kind


def test_only_a_successful_reply_can_be_accepted() -> None:
    with pytest.raises(ValueError):
        accept(start_chat("dog", "Scratching"), ApiResult(error="The request timed out."))
