"""Pure checks shared by the opt-in live journey evaluation."""

from __future__ import annotations

import re

_NORMALITY_TERM = re.compile(r"\b(?:normal|expected)\b", re.IGNORECASE)
_CONCERN_TERM = re.compile(r"\b(?:concerning|abnormal)\b", re.IGNORECASE)


def query_compares_normality_with_concern(query: str) -> bool:
    """Require an explicit term from both sides of the intended comparison."""
    return _NORMALITY_TERM.search(query) is not None and _CONCERN_TERM.search(query) is not None


def normal_control_assessment_passes(
    payload: dict[str, object], expected_reported: list[str]
) -> bool:
    """Accept J4 only when the bounded result contains no problem or invented owner fact."""
    if payload.get("kind") != "assessment":
        return False
    assessment = payload.get("assessment")
    if not isinstance(assessment, dict):
        return False
    return (
        assessment.get("outcome") == "nothing_flagged"
        and assessment.get("possible_areas") == []
        and assessment.get("what_you_reported") == expected_reported
    )
