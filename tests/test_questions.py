"""The fixed prefix is product policy, not model wording."""

from backend.questions import STANDARD_QUESTIONS, next_standard_question


def test_the_three_standard_questions_are_short_and_ordered() -> None:
    assert [(item.id, item.text) for item in STANDARD_QUESTIONS] == [
        ("duration", "How long has this been happening?"),
        ("previous_occurrence", "Has this happened before?"),
        ("pattern", "Is it happening constantly, or does it come and go?"),
    ]


def test_question_lookup_ends_after_the_fixed_prefix() -> None:
    assert next_standard_question(0) == STANDARD_QUESTIONS[0]
    assert next_standard_question(2) == STANDARD_QUESTIONS[2]
    assert next_standard_question(3) is None
