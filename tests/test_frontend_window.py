"""Critical owner actions in the offscreen PySide6 window."""

from __future__ import annotations

import pytest

from conftest import assessment_payload
from frontend.local.api_client import ApiResult, ChatApiClient
from frontend.local.app import ChatWindow

FIRST_QUESTION = ApiResult(kind="question", reply="How long has this been happening?")


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch, qapplication):
    sent: list[tuple[int, dict[str, object]]] = []

    def capture_send(client: ChatApiClient, request_id: int, body: dict[str, object]) -> None:
        sent.append((request_id, body))

    monkeypatch.setattr(ChatApiClient, "send", capture_send)
    chat_window = ChatWindow("http://127.0.0.1:8000")
    yield chat_window, sent
    chat_window.close()


def test_window_starts_then_advances_only_after_a_success(window) -> None:
    chat_window, sent = window
    chat_window.concern.setText("My dog scratched one ear today.")

    chat_window._send()
    chat_window._handle_result(1, FIRST_QUESTION)
    chat_window.answer.setPlainText("Yesterday")
    chat_window._send()

    assert sent[0][1] == {
        "intake": {"species": "dog", "concern": "My dog scratched one ear today."},
        "history": [],
    }
    assert sent[1][1]["history"] == [
        {"role": "assistant", "content": FIRST_QUESTION.reply},
        {"role": "user", "content": "Yesterday"},
    ]


def test_window_retains_a_draft_until_the_owner_retries(window) -> None:
    chat_window, sent = window
    chat_window.concern.setText("My dog scratched one ear today.")
    chat_window._send()
    chat_window._handle_result(1, FIRST_QUESTION)
    chat_window.answer.setPlainText("Yesterday")
    chat_window._send()
    failed_request = sent[-1][1]
    chat_window._handle_result(2, ApiResult(error="The request timed out. Please try again."))

    assert chat_window.retry_button.isHidden() is False
    chat_window.retry_button.click()

    assert chat_window.answer.toPlainText() == "Yesterday"
    assert sent[-1][1] == failed_request


def test_try_again_after_a_failed_first_request_resends_the_concern(window) -> None:
    chat_window, sent = window
    chat_window.concern.setText("My dog scratched one ear today.")
    chat_window._send()
    chat_window._handle_result(1, ApiResult(error="Could not reach the assistant service."))

    chat_window.retry_button.click()

    assert len(sent) == 2
    assert sent[1][1] == sent[0][1]


def test_an_over_long_concern_is_refused_rather_than_cut_short(window) -> None:
    chat_window, sent = window
    # The warning sign is at the very end, past the backend's 1000-character limit.
    concern = "My dog has been restless all day. " * 29 + "She is now struggling to breathe."
    chat_window.concern.setText(concern)

    chat_window._send()

    assert len(concern) > 1000
    assert sent == []
    assert chat_window.error_label.text() == "Keep the concern under 1000 characters."
    assert chat_window.concern.text() == concern


def test_a_pending_request_shows_the_concern_and_thinking(window) -> None:
    chat_window, _ = window
    chat_window.concern.setText("My dog scratched one ear today.")

    chat_window._send()

    shown = chat_window.transcript.toPlainText()
    assert "My dog scratched one ear today." in shown
    assert "Thinking" in shown


def test_a_finished_assessment_shows_its_sections_and_offers_a_new_concern(window) -> None:
    chat_window, _ = window
    chat_window.concern.setText("My dog keeps scratching.")
    chat_window._send()

    chat_window._handle_result(1, ApiResult(kind="assessment", assessment=assessment_payload()))

    shown = chat_window.transcript.toPlainText()
    for label in (
        "What you reported",
        "Possible areas",
        "Suggested actions",
        "Questions for your veterinarian",
        "Sources",
    ):
        assert label in shown
    assert 'href="https://vet.cornell.edu/itchy-skin"' in chat_window.transcript.toHtml()
    assert chat_window.transcript.openExternalLinks() is True
    assert chat_window.new_concern_button.isHidden() is False
    assert chat_window.send_button.isHidden() is True


def test_window_ends_or_ignores_an_abandoned_turn(window) -> None:
    chat_window, sent = window
    chat_window._send()
    assert chat_window.error_label.text() == "Enter a concern."

    chat_window.concern.setText("My dog scratched one ear today.")
    chat_window._send()
    chat_window._new_concern()
    chat_window._handle_result(1, ApiResult(kind="question", reply="Late question"))

    assert chat_window.transcript.toPlainText() == ""
    assert chat_window.state.intake is None
    assert chat_window.concern.text() == ""
