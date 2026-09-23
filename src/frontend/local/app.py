"""A small native desktop client for the local pet-concern chat.

The chat state is a frozen dataclass changed only by four functions: `start_chat`,
`request_body`, `accept` and `reject`. The window stores the latest state and redraws every widget
from it, so what the owner sees always matches the state.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from html import escape
from typing import Any, Literal

from PySide6.QtGui import QTextCursor
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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from frontend.local.api_client import ApiResult, ChatApiClient

# The backend accepts at most this many characters for the concern and for each answer.
MAX_TEXT_CHARS = 1000

# Bubble colours as (background, text).
OWNER_COLOURS = ("#2f5fb3", "#ffffff")
VETAI_COLOURS = ("#eef1f6", "#1f2733")
URGENT_COLOURS = ("#fbe3df", "#7a1f12")
# Set explicitly because Qt's dark-mode link colour is unreadable on the light VetAI bubble.
LINK_COLOUR = "#1d4ed8"

# The same titles the browser client shows.
OUTCOME_TITLES = {
    "possible_problem": "Possible problem — see a veterinarian",
    "nothing_flagged": "Nothing flagged",
}


@dataclass(frozen=True)
class Bubble:
    """One message in the transcript."""

    author: Literal["owner", "vetai"]
    text: str = ""
    kind: Literal["message", "emergency_notice", "assessment"] = "message"
    assessment: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatState:
    """Everything the window shows. `history` holds only pairs the backend has accepted."""

    intake: dict[str, str] | None = None
    history: tuple[dict[str, str], ...] = ()
    current_question: str | None = None
    draft_answer: str = ""
    transcript: tuple[Bubble, ...] = ()
    error: str | None = None
    pending: bool = False
    ended: bool = False


def start_chat(species: str, concern: str) -> ChatState:
    """Start a fresh chat. The concern shows straight away as the owner's first bubble."""
    return ChatState(
        intake={"species": species, "concern": concern},
        transcript=(Bubble("owner", concern),),
    )


def request_body(state: ChatState) -> dict[str, Any]:
    """The whole chat so far, including the draft answer the backend has not accepted yet."""
    if state.intake is None:
        raise ValueError("the chat has not been started")
    history = list(state.history)
    if state.current_question is not None:
        history += [
            {"role": "assistant", "content": state.current_question},
            {"role": "user", "content": state.draft_answer},
        ]
    return {"intake": dict(state.intake), "history": history}


def accept(state: ChatState, result: ApiResult) -> ChatState:
    """Move the chat on after a successful reply. A question commits the pair it answered."""
    if state.current_question is not None:
        answered_pair = (
            {"role": "assistant", "content": state.current_question},
            {"role": "user", "content": state.draft_answer},
        )
        answer_bubble = (Bubble("owner", state.draft_answer),)
    else:
        answered_pair, answer_bubble = (), ()

    if result.kind == "question" and result.reply is not None:
        return replace(
            state,
            history=state.history + answered_pair,
            current_question=result.reply,
            draft_answer="",
            transcript=state.transcript + answer_bubble + (Bubble("vetai", result.reply),),
            error=None,
            pending=False,
        )

    if result.kind == "emergency_notice" and result.reply is not None:
        last_bubble = Bubble("vetai", result.reply, kind="emergency_notice")
    elif result.kind == "assessment" and result.assessment is not None:
        last_bubble = Bubble("vetai", kind="assessment", assessment=result.assessment)
    else:
        raise ValueError("only a successful reply can be accepted")
    return replace(
        state,
        current_question=None,
        transcript=state.transcript + answer_bubble + (last_bubble,),
        error=None,
        pending=False,
        ended=True,
    )


def reject(state: ChatState, error: str) -> ChatState:
    """Show the error and keep everything else, including the draft answer, as it was."""
    return replace(state, error=error, pending=False)


def transcript_html(bubbles: tuple[Bubble, ...], pending: bool) -> str:
    """The whole chat as HTML: owner bubbles on the right, VetAI bubbles on the left."""
    rows = [_bubble_html(bubble) for bubble in bubbles]
    if pending:
        rows.append(_row_html("<i>Thinking…</i>", VETAI_COLOURS, owner=False))
    return "".join(rows)


def _bubble_html(bubble: Bubble) -> str:
    if bubble.author == "owner":
        return _row_html(f"<b>You</b><br>{_text(bubble.text)}", OWNER_COLOURS, owner=True)
    if bubble.kind == "assessment":
        return _row_html(_assessment_html(bubble.assessment), VETAI_COLOURS, owner=False, wide=True)
    colours = URGENT_COLOURS if bubble.kind == "emergency_notice" else VETAI_COLOURS
    return _row_html(f"<b>VetAI</b><br>{_text(bubble.text)}", colours, owner=False)


def _row_html(content: str, colours: tuple[str, str], *, owner: bool, wide: bool = False) -> str:
    """One row: the bubble, plus an empty cell that pushes it to the left or right."""
    background, text_colour = colours
    bubble = f'<td bgcolor="{background}" style="color: {text_colour}">{content}</td>'
    spacer = "" if wide else '<td width="25%"></td>'
    cells = spacer + bubble if owner else bubble + spacer
    return f'<table width="100%" cellspacing="4" cellpadding="8"><tr>{cells}</tr></table>'


def _assessment_html(assessment: dict[str, Any]) -> str:
    """The labelled sections of an assessment, in the order the owner reads them."""
    title = OUTCOME_TITLES[assessment["outcome"]]
    reported = [_text(item) for item in assessment["what_you_reported"]]
    questions = _cited(assessment["questions_for_veterinarian"])
    sources = [_source_html(source) for source in assessment["sources"]]

    parts = [f"<b>{escape(title)}</b>", f"<p>{_text(assessment['outcome_wording'])}</p>"]
    parts.append(_section_html("What you reported", reported))
    if assessment["possible_areas"]:
        parts.append(_section_html("Possible areas", _cited(assessment["possible_areas"])))
    parts.append(_section_html("Suggested actions", _cited(assessment["suggested_actions"])))
    parts.append(_section_html("Questions for your veterinarian", questions))
    parts.append(_section_html("Sources", sources))
    parts.append(f"<p><i>{_text(assessment['disclaimer'])}</i></p>")
    return "".join(parts)


def _section_html(title: str, items: list[str]) -> str:
    rows = "".join(f"<li>{item}</li>" for item in items)
    return f"<p><b>{escape(title)}</b></p><ul>{rows}</ul>"


def _cited(items: list[dict[str, Any]]) -> list[str]:
    """Each item's text followed by the source IDs it cites, for example "[S1, S2]"."""
    return [f"{_text(item['text'])} [{escape(', '.join(item['source_ids']))}]" for item in items]


def _source_html(source: dict[str, str]) -> str:
    url, title = escape(source["url"]), escape(source["title"])
    link = f'<a href="{url}" style="color: {LINK_COLOUR}">{title}</a>'
    return f"[{escape(source['source_id'])}] {link} — {escape(source['organisation'])}"


def _text(value: str) -> str:
    """Owner or model text made safe for HTML, keeping its line breaks."""
    return escape(value).replace("\n", "<br>")


class ChatWindow(QMainWindow):
    """The visible desktop chat. All network work stays in `ChatApiClient`."""

    def __init__(self, api_url: str) -> None:
        super().__init__()
        self.setWindowTitle("VetAI pet concern demo")
        self.resize(720, 760)

        self._request_id = 0
        self._api = ChatApiClient(api_url)
        self._api.result_ready.connect(self._handle_result)

        self._build_ui()
        self._show(ChatState())

    def _build_ui(self) -> None:
        self.species = QComboBox()
        self.species.addItems(["dog", "cat"])
        # No setMaxLength: it would silently cut a pasted concern, and the cut-off end could hold
        # the words the emergency check looks for. `_send` refuses an over-long concern instead.
        self.concern = QLineEdit()
        self.concern.setPlaceholderText("What is worrying you about your pet?")
        intake_form = QFormLayout()
        intake_form.addRow("Species", self.species)
        intake_form.addRow("Concern", self.concern)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)  # a source link opens in the web browser
        self.transcript.setPlaceholderText(
            "Describe what you are seeing, then select Send concern."
        )

        self.answer = QPlainTextEdit()
        self.answer.setPlaceholderText("Your answer")
        self.answer.setMaximumHeight(100)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #9b1c1c;")

        self.send_button = QPushButton()
        self.send_button.clicked.connect(self._send)
        self.retry_button = QPushButton("Try again")
        self.retry_button.clicked.connect(self._send)
        self.new_concern_button = QPushButton("New concern")
        self.new_concern_button.clicked.connect(self._new_concern)
        buttons = QHBoxLayout()
        buttons.addWidget(self.send_button)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.new_concern_button)

        layout = QVBoxLayout()
        layout.addLayout(intake_form)
        layout.addWidget(self.transcript)
        layout.addWidget(self.answer)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _send(self) -> None:
        """Send the concern until the first question arrives, then the answer to each question."""
        if self.state.pending or self.state.ended:
            return

        if self.state.current_question is None:
            concern = self.concern.text().strip()
            if not concern:
                self._show(reject(self.state, "Enter a concern."))
                return
            if len(concern) > MAX_TEXT_CHARS:
                too_long = f"Keep the concern under {MAX_TEXT_CHARS} characters."
                self._show(reject(self.state, too_long))
                return
            next_state = start_chat(self.species.currentText(), concern)
        else:
            answer = self.answer.toPlainText().strip()
            if not answer:
                self._show(reject(self.state, "Enter an answer."))
                return
            if len(answer) > MAX_TEXT_CHARS:
                too_long = f"Keep the answer under {MAX_TEXT_CHARS} characters."
                self._show(reject(self.state, too_long))
                return
            next_state = replace(self.state, draft_answer=answer)

        self._request_id += 1
        self._show(replace(next_state, error=None, pending=True))
        self._api.send(self._request_id, request_body(self.state))

    def _handle_result(self, request_id: int, result: ApiResult) -> None:
        """Apply a reply, unless it answers a request the owner has already moved on from."""
        if request_id != self._request_id:
            return
        if result.error is not None:
            self._show(reject(self.state, result.error))
        elif result.issues:
            issues = "\n".join(f"{issue['field']}: {issue['message']}" for issue in result.issues)
            self._show(reject(self.state, issues))
        else:
            self.answer.clear()
            self._show(accept(self.state, result))

    def _new_concern(self) -> None:
        """Clear everything. Moving the request id on means a late reply is ignored."""
        self._request_id += 1
        self.species.setCurrentText("dog")
        self.concern.clear()
        self.answer.clear()
        self._show(ChatState())

    def _show(self, state: ChatState) -> None:
        """Store the new state, then make every widget match it."""
        self.state = state
        awaiting_answer = state.current_question is not None and not state.ended
        intake_editable = state.current_question is None and not state.pending and not state.ended

        self.species.setEnabled(intake_editable)
        self.concern.setEnabled(intake_editable)
        self.transcript.setHtml(transcript_html(state.transcript, state.pending))
        # The view follows the text cursor, so moving it to the end keeps the newest bubble in view.
        self.transcript.moveCursor(QTextCursor.MoveOperation.End)
        self.answer.setEnabled(awaiting_answer and not state.pending)
        self.send_button.setText("Send answer" if awaiting_answer else "Send concern")
        self.send_button.setEnabled(not state.pending)
        self.send_button.setVisible(not state.ended)
        self.retry_button.setVisible(state.error is not None and not state.pending)
        self.new_concern_button.setVisible(state.ended)
        self.error_label.setText(state.error or "")


def main() -> int:
    """Launch the desktop process independently from the backend server."""
    application = QApplication(sys.argv)
    api_url = os.environ.get("BACKEND_API_URL", "http://127.0.0.1:8000")
    window = ChatWindow(api_url)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
