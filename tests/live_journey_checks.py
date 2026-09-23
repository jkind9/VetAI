"""Pure checks shared by the opt-in live journey evaluation."""

from __future__ import annotations

import re

_NORMALITY_TERM = re.compile(r"\b(?:normal|expected)\b", re.IGNORECASE)
_CONCERN_TERM = re.compile(r"\b(?:concerning|abnormal)\b", re.IGNORECASE)


def query_compares_normality_with_concern(query: str) -> bool:
    """Require an explicit term from both sides of the intended comparison."""
    return _NORMALITY_TERM.search(query) is not None and _CONCERN_TERM.search(query) is not None
