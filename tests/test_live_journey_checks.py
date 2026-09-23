"""Deterministic tests for live-journey evaluation predicates."""

from __future__ import annotations

import pytest

from live_journey_checks import query_compares_normality_with_concern


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("dog panting at rest normal versus concerning veterinary", True),
        ("dog panting expected or abnormal", True),
        ("dog panting abnormal", False),
        ("unexpected abnormal panting", False),
        ("dog panting normal after exercise", False),
    ],
)
def test_query_comparison_requires_whole_words_from_both_sides(
    query: str, expected: bool
) -> None:
    assert query_compares_normality_with_concern(query) is expected
