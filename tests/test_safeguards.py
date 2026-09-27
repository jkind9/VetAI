"""The curated emergency phrases: what fires, what does not, and where the line sits.

Cases come from documentation/test-cases.md sections A and B. A passing test here means the
matcher behaves as specified. It does not mean an unmatched sentence is safe.
"""

from __future__ import annotations

import pytest

from backend.safeguards import find_emergency


@pytest.mark.parametrize(
    ("text", "expected_rule"),
    [
        # E1-E4: one clear positive per category.
        ("My dog is struggling to breathe.", "breathing_difficulty"),
        ("My dog collapsed just now.", "collapse"),
        ("My dog may have swallowed a medication.", "suspected_ingestion"),
        ("My dog keeps trying but cannot urinate.", "cannot_urinate"),
        # E7: capitals, punctuation and a contraction do not hide a listed phrase.
        ("MY DOG IS STRUGGLING TO BREATHE!", "breathing_difficulty"),
        ("My dog has collapsed.", "collapse"),
        ("My cat can't urinate.", "cannot_urinate"),
        # E6: uncertain possible ingestion still gets the notice. The denial attaches to
        # "think", not to the swallowing.
        ("I don't think she swallowed any pills, but the packet is open.", "suspected_ingestion"),
        # E8: owner-written duration text is scanned like any other owner text.
        ("Since she collapsed this morning.", "collapse"),
    ],
)
def test_listed_warning_phrases_match(text: str, expected_rule: str) -> None:
    match = find_emergency([text])
    assert match is not None, f"expected {expected_rule} to fire on {text!r}"
    assert match.rule == expected_rule


@pytest.mark.parametrize(
    "text",
    [
        # O3: the phrase appears, but the owner is denying it.
        "My dog has an itchy ear, but is not having difficulty breathing.",
        # O9: near misses. None of these say the pet is safe; they just are not these rules.
        "The sofa collapsed near my dog",
        "My dog is urinating more often than usual",
        "She sniffed a sealed medication bottle but did not swallow anything.",
        # An ordinary concern with no listed phrase at all.
        "My dog scratched one ear today.",
        "My dog has been panting for a few minutes after vigorous play.",
        # Whole-word matching: duration and anatomy words must not contain warning verbs.
        "Maybe a week.",
        "My dog has been trying to wait a week.",
        "Her heart rate went up after her new medication.",
    ],
)
def test_ordinary_text_does_not_fire_a_rule(text: str) -> None:
    assert find_emergency([text]) is None


def test_the_first_matching_text_is_reported() -> None:
    """A warning sign in a later answer still counts, and the rule is named for tracking."""
    match = find_emergency(
        ["My dog seems quieter than usual.", "Now she is struggling to breathe."]
    )
    assert match is not None
    assert match.rule == "breathing_difficulty"
    assert match.phrase.lower() == "struggling to breathe"


def test_empty_and_blank_texts_are_skipped() -> None:
    assert find_emergency([]) is None
    assert find_emergency(["", "   "]) is None
