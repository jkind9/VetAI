"""Critical owner actions in the offscreen PySide6 window."""

from __future__ import annotations

import pytest

from frontend.api_client import ApiResult, ChatApiClient
from frontend.app import ChatWindow


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
    chat_window._handle_result(1, ApiResult(kind="question", reply="When did it start?"))
    chat_window.answer.setPlainText("Yesterday")
    chat_window._send()

    assert sent[0][1]["history"] == []
    assert sent[1][1]["history"] == [
        {"role": "assistant", "content": "When did it start?"},
        {"role": "user", "content": "Yesterday"},
    ]


def test_window_retains_a_draft_until_the_owner_retries(window) -> None:
    chat_window, sent = window
    chat_window.concern.setText("My dog scratched one ear today.")
    chat_window._send()
    chat_window._handle_result(1, ApiResult(kind="question", reply="When did it start?"))
    chat_window.answer.setPlainText("Yesterday")
    chat_window._send()
    failed_request = sent[-1][1]
    chat_window._handle_result(2, ApiResult(error="The request timed out. Please try again."))

    assert chat_window.retry_button.isHidden() is False
    chat_window._send()

    assert chat_window.answer.toPlainText() == "Yesterday"
    assert sent[-1][1] == failed_request


def test_window_ends_or_ignores_an_abandoned_turn(window) -> None:
    chat_window, sent = window
    chat_window._send()
    assert chat_window.error_label.text() == "Enter a concern."

    chat_window.concern.setText("My dog scratched one ear today.")
    chat_window._send()
    chat_window._new_concern()
    chat_window._handle_result(1, ApiResult(kind="question", reply="Late question"))

    assert chat_window.conversation.toPlainText() == ""
    assert chat_window.state.intake is None
    assert chat_window.concern.text() == ""
    assert chat_window.duration.text() == "unknown"
