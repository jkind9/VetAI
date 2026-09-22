"""A small native desktop client for the local pet-concern question flow."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.api_client import ApiResult, ChatApiClient


@dataclass
class ChatState:
    """The current owner draft and only the question-answer pairs the backend accepted."""

    intake: dict[str, str] | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    current_question: str | None = None
    draft_answer: str = ""
    error: str | None = None
    ended: bool = False
    pending: bool = False

    def start(self, intake: dict[str, str]) -> None:
        """Start a fresh concern without retaining a previous chat's history or result."""
        self.intake = dict(intake)
        self.history = []
        self.current_question = None
        self.draft_answer = ""
        self.error = None
        self.ended = False
        self.pending = False

    def request_body(self) -> dict[str, object]:
        """Build a snapshot that includes the current draft but does not accept it yet."""
        if self.intake is None:
            raise RuntimeError("chat intake has not been started")

        history = list(self.history)
        if self.current_question is not None:
            history.extend(
                [
                    {"role": "assistant", "content": self.current_question},
                    {"role": "user", "content": self.draft_answer},
                ]
            )
        return {"intake": dict(self.intake), "history": history}

    def accept(self, result: ApiResult) -> None:
        """Advance only after a successful model or emergency response."""
        if result.kind == "question" and result.reply is not None:
            if self.current_question is not None:
                self.history.extend(
                    [
                        {"role": "assistant", "content": self.current_question},
                        {"role": "user", "content": self.draft_answer},
                    ]
                )
            self.current_question = result.reply
            self.draft_answer = ""
            self.error = None
        elif result.kind in {"summary", "emergency_notice"}:
            self.current_question = None
            self.error = None
            self.ended = True
        else:
            raise ValueError("only successful replies can be accepted")
        self.pending = False

    def reject(self, error: str) -> None:
        """Keep the current draft untouched until the owner changes it or retries."""
        self.error = error
        self.pending = False


class ChatWindow(QMainWindow):
    """The visible desktop flow; all network work stays in ``ChatApiClient``."""

    def __init__(self, api_url: str) -> None:
        super().__init__()
        self.setWindowTitle("VetAI pet concern demo")
        self.resize(720, 680)

        self.state = ChatState()
        self._request_id = 0
        self._api = ChatApiClient(api_url)
        self._api.result_ready.connect(self._handle_result)

        self._build_ui()
        self._refresh_controls()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        intake_form = QFormLayout()
        self.species = QComboBox()
        self.species.addItems(["dog", "cat"])
        self.concern = QLineEdit()
        self.concern.setPlaceholderText("What concerns you about your pet?")
        self.duration = QLineEdit("unknown")
        self.previous_occurrence = QComboBox()
        self.previous_occurrence.addItems(["unknown", "yes", "no"])
        self.pattern = QComboBox()
        self.pattern.addItems(["unknown", "constant", "intermittent"])
        intake_form.addRow("Species", self.species)
        intake_form.addRow("Concern", self.concern)
        intake_form.addRow("Duration", self.duration)
        intake_form.addRow("Happened before", self.previous_occurrence)
        intake_form.addRow("Pattern", self.pattern)
        layout.addLayout(intake_form)

        self.conversation = QPlainTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setPlaceholderText(
            "The assistant's question or summary will appear here."
        )
        layout.addWidget(self.conversation)

        self.answer = QPlainTextEdit()
        self.answer.setPlaceholderText("Type your answer to the displayed question.")
        layout.addWidget(self.answer)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #9b1c1c;")
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        self.send_button = QPushButton("Start chat")
        self.send_button.clicked.connect(self._send)
        self.retry_button = QPushButton("Try again")
        self.retry_button.clicked.connect(self._send)
        self.new_concern_button = QPushButton("New concern")
        self.new_concern_button.clicked.connect(self._new_concern)
        buttons.addWidget(self.send_button)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.new_concern_button)
        layout.addLayout(buttons)

        self.setCentralWidget(central)

    def _intake(self) -> dict[str, str]:
        return {
            "species": self.species.currentText(),
            "concern": self.concern.text(),
            "duration": self.duration.text(),
            "previous_occurrence": self.previous_occurrence.currentText(),
            "pattern": self.pattern.currentText(),
        }

    def _send(self) -> None:
        if self.state.pending or self.state.ended:
            return
        if self.state.current_question is None and not self.state.history:
            if not self.concern.text().strip():
                self.state.reject("Enter a concern.")
                self._refresh_controls()
                return
            self.state.start(self._intake())
        else:
            self.state.draft_answer = self.answer.toPlainText()
            if not self.state.draft_answer.strip():
                self.state.reject("Enter an answer.")
                self._refresh_controls()
                return

        self.state.pending = True
        self.state.error = None
        self._request_id += 1
        self._api.send(self._request_id, self.state.request_body())
        self._refresh_controls()

    def _handle_result(self, request_id: int, result: ApiResult) -> None:
        if request_id != self._request_id or self.state.ended:
            return
        if result.error is not None:
            self.state.reject(result.error)
        elif result.issues:
            issues = (f"{item['field']}: {item['message']}" for item in result.issues)
            self.state.reject("\n".join(issues))
        else:
            if self.state.current_question is not None:
                self.conversation.appendPlainText(f"You: {self.state.draft_answer}")
            self.state.accept(result)
            self.conversation.appendPlainText(f"Assistant: {result.reply}")
            self.answer.clear()
        self._refresh_controls()

    def _new_concern(self) -> None:
        self._request_id += 1
        self.state = ChatState()
        self.species.setCurrentText("dog")
        self.concern.clear()
        self.duration.setText("unknown")
        self.previous_occurrence.setCurrentText("unknown")
        self.pattern.setCurrentText("unknown")
        self.conversation.clear()
        self.answer.clear()
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        waiting_for_answer = self.state.current_question is not None and not self.state.ended
        self.answer.setEnabled(waiting_for_answer and not self.state.pending)
        self.send_button.setEnabled(not self.state.pending and not self.state.ended)
        self.send_button.setText("Send" if waiting_for_answer else "Start chat")
        self.retry_button.setVisible(self.state.error is not None and not self.state.pending)
        self.new_concern_button.setVisible(self.state.ended)
        self.error_label.setText(self.state.error or "")


def main() -> int:
    """Launch the desktop process independently from the backend server."""
    application = QApplication(sys.argv)
    api_url = os.environ.get("BACKEND_API_URL", "http://127.0.0.1:8000")
    window = ChatWindow(api_url)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
