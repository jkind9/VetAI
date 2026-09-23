"""Opt-in live smoke test for one reviewed veterinary source."""

from __future__ import annotations

import os

import pytest

from backend.approved_sources import ApprovedSourceCatalog
from backend.search import HttpPageFetcher

MSD_EMERGENCY_URL = (
    "https://www.msdvetmanual.com/special-pet-topics/emergencies/"
    "what-to-do-in-a-dog-or-cat-emergency"
)
EXPECTED_TERMS = ("heat stroke", "rapid panting", "water")


@pytest.mark.skipif(
    os.getenv("VETAI_RUN_LIVE_SEARCH_SMOKE") != "1",
    reason="set VETAI_RUN_LIVE_SEARCH_SMOKE=1 to run the live search smoke test",
)
def test_msd_emergency_page_is_allowlisted_and_fetchable() -> None:
    catalog = ApprovedSourceCatalog.load()
    assert catalog.match(MSD_EMERGENCY_URL) is not None

    page = HttpPageFetcher(catalog, timeout=20.0).fetch(MSD_EMERGENCY_URL)

    assert catalog.match(page.final_url) is not None
    content = page.text.casefold()
    missing_terms = [term for term in EXPECTED_TERMS if term not in content]
    assert not missing_terms, f"MSD page omitted expected terms: {missing_terms}"
