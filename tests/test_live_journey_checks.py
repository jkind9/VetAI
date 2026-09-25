"""Deterministic tests for live-journey evaluation predicates."""

from __future__ import annotations

import pytest

from live_journey_checks import (
    normal_control_assessment_passes,
    query_compares_normality_with_concern,
)

EXPECTED_NORMAL_REPORT = [
    "Concern: My dog is breathing completely normally",
    "Duration: forever",
    "Previous occurrence: yes, its always been normal",
    "Pattern: constantly normal",
    "Additional detail 1: no",
]


def _normal_control_payload() -> dict[str, object]:
    return {
        "kind": "assessment",
        "assessment": {
            "outcome": "nothing_flagged",
            "what_you_reported": list(EXPECTED_NORMAL_REPORT),
            "possible_areas": [],
        },
    }


def test_normal_control_accepts_only_the_expected_bounded_assessment() -> None:
    assert normal_control_assessment_passes(
        _normal_control_payload(), EXPECTED_NORMAL_REPORT
    )


@pytest.mark.parametrize("failure", ["outcome", "possible_area", "invented_fact", "not_assessment"])
def test_normal_control_rejects_unsafe_or_invented_results(failure: str) -> None:
    payload = _normal_control_payload()
    assessment = payload["assessment"]
    assert isinstance(assessment, dict)
    if failure == "outcome":
        assessment["outcome"] = "possible_problem"
    elif failure == "possible_area":
        assessment["possible_areas"] = [{"text": "Respiratory disease", "source_ids": ["S1"]}]
    elif failure == "invented_fact":
        assessment["what_you_reported"] = [*EXPECTED_NORMAL_REPORT, "Rate: 20 breaths/minute"]
    else:
        payload["kind"] = "question"

    assert not normal_control_assessment_passes(payload, EXPECTED_NORMAL_REPORT)


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
