"""The desktop keeps drafts local until a request succeeds."""

from __future__ import annotations

from frontend.app import ChatState
from frontend.api_client import ApiResult


def _intake() -> dict[str, str]:
    return {
        "species": "dog",
        "concern": "My dog scratched one ear today.",
        "duration": "unknown",
        "previous_occurrence": "unknown",
        "pattern": "unknown",
    }


def test_first_request_contains_intake_and_no_history() -> None:
    state = ChatState()
    state.start(_intake())

    assert state.request_body() == {"intake": _intake(), "history": []}


def test_question_success_commits_only_the_accepted_pair() -> None:
    state = ChatState()
    state.start(_intake())
    state.accept(ApiResult(kind="question", reply="When did it start?"))
    state.draft_answer = "Yesterday"

    snapshot = state.request_body()
    state.accept(ApiResult(kind="question", reply="Has it changed since then?"))

    assert snapshot["history"] == [
        {"role": "assistant", "content": "When did it start?"},
        {"role": "user", "content": "Yesterday"},
    ]
    assert state.history == snapshot["history"]
    assert state.current_question == "Has it changed since then?"
    assert state.draft_answer == ""


def test_failure_keeps_the_draft_and_does_not_advance_history() -> None:
    state = ChatState()
    state.start(_intake())
    state.accept(ApiResult(kind="question", reply="When did it start?"))
    state.draft_answer = "Yesterday"
    before = state.request_body()

    state.reject("The request timed out. Please try again.")

    assert state.request_body() == before
    assert state.draft_answer == "Yesterday"
    assert state.error == "The request timed out. Please try again."


def test_summary_or_emergency_notice_ends_the_chat() -> None:
    state = ChatState()
    state.start(_intake())

    state.accept(ApiResult(kind="emergency_notice", reply="Please contact a veterinarian."))

    assert state.ended is True
    assert state.current_question is None
