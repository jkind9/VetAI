"""Approved-source enforcement and query privacy are deterministic policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.approved_sources import (
    DEFAULT_SOURCE_CATALOG_PATH,
    ApprovedSourceCatalog,
)
from backend.schemas import ModelOutputError, SearchPlan
from backend.search import ApprovedSourceSearcher, FetchedPage, query_is_safe


class FakeSearchClient:
    def __init__(self, results: list[dict[str, str]]) -> None:
        self.results = results
        self.queries: list[str] = []

    def text(self, query: str, **kwargs) -> list[dict[str, str]]:
        self.queries.append(query)
        return list(self.results)


class SequencedSearchClient:
    """Return or raise each scripted provider outcome in call order."""

    def __init__(self, outcomes: list[list[dict[str, str]] | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.queries: list[str] = []

    def text(self, query: str, **kwargs) -> list[dict[str, str]]:
        self.queries.append(query)
        if not self.outcomes:
            raise AssertionError("unexpected search-provider call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return list(outcome)


class FakePageFetcher:
    def __init__(self, pages: dict[str, FetchedPage | Exception]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchedPage:
        self.urls.append(url)
        result = self.pages[url]
        if isinstance(result, Exception):
            raise result
        return result


def test_committed_source_catalog_contains_the_reviewed_domains() -> None:
    catalog = ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH)

    assert catalog.domains == {
        "vet.cornell.edu",
        "rvc.ac.uk",
        "msdvetmanual.com",
        "aspca.org",
        "pdsa.org.uk",
        "bluecross.org.uk",
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://vet.cornell.edu/article",
        "https://www.rvc.ac.uk/advice",
        "https://www.aspca.org/news/example",
    ],
)
def test_https_exact_hosts_and_subdomains_are_approved(url: str) -> None:
    assert ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH).match(url) is not None


@pytest.mark.parametrize(
    "url",
    [
        "http://vet.cornell.edu/article",
        "https://aspca.org.example.com/article",
        "https://example.com/?next=https://aspca.org",
        "not-a-url",
    ],
)
def test_insecure_or_lookalike_urls_are_rejected(url: str) -> None:
    assert ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH).match(url) is None


@pytest.mark.parametrize(
    "query",
    [
        "https://example.com dog shaking",
        "owner@example.com dog shaking",
        "+44 7700 900123 dog shaking",
        "dog shaking call 020 7946 0958",
    ],
)
def test_queries_with_contact_or_url_data_are_blocked(query: str) -> None:
    assert query_is_safe(query) is False


def test_search_filters_off_list_results_redirects_and_duplicates() -> None:
    approved = "https://vet.cornell.edu/dog-ear"
    off_list = "https://example.com/dog-ear"
    redirecting = "https://aspca.org/redirect"
    client = FakeSearchClient(
        [
            {"title": "Cornell", "href": approved, "body": "Search snippet"},
            {"title": "Duplicate", "href": approved, "body": "Duplicate snippet"},
            {"title": "Off list", "href": off_list, "body": "No"},
            {"title": "Redirect", "href": redirecting, "body": "No"},
        ]
    )
    fetcher = FakePageFetcher(
        {
            approved: FetchedPage(final_url=approved, text="Useful veterinary page text"),
            redirecting: FetchedPage(final_url=off_list, text="Unapproved redirect text"),
        }
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=fetcher,
    )

    results = searcher.search(SearchPlan(queries=["dog ear scratching veterinary"]))

    assert len(results) == 1
    assert results[0].source_id == "S1"
    assert str(results[0].url) == approved
    assert results[0].excerpt == "Useful veterinary page text"
    assert off_list not in fetcher.urls
    assert client.queries and "site:vet.cornell.edu" in client.queries[0]


def test_one_fetch_failure_does_not_hide_other_approved_evidence() -> None:
    first = "https://vet.cornell.edu/one"
    second = "https://www.rvc.ac.uk/two"
    client = FakeSearchClient(
        [
            {"title": "One", "href": first, "body": "one"},
            {"title": "Two", "href": second, "body": "two"},
        ]
    )
    fetcher = FakePageFetcher(
        {
            first: RuntimeError("page unavailable"),
            second: FetchedPage(final_url=second, text="usable evidence"),
        }
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=fetcher,
    )

    results = searcher.search(SearchPlan(queries=["dog concern veterinary"]))

    assert [item.title for item in results] == ["Two"]


def test_query_provider_failure_does_not_discard_earlier_approved_result() -> None:
    approved = "https://vet.cornell.edu/one"
    client = SequencedSearchClient(
        [
            [{"title": "One", "href": approved, "body": "one"}],
            TimeoutError("provider timed out"),
        ]
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=FakePageFetcher(
            {approved: FetchedPage(final_url=approved, text="usable evidence")}
        ),
    )

    results = searcher.search(SearchPlan(queries=["dog concern one", "dog concern two"]))

    assert [item.title for item in results] == ["One"]
    assert len(client.queries) == 2


def test_all_provider_failures_retry_the_same_plan_once_before_succeeding() -> None:
    approved = "https://vet.cornell.edu/recovered"
    client = SequencedSearchClient(
        [
            TimeoutError("provider timed out"),
            [{"title": "Recovered", "href": approved, "body": "recovered"}],
        ]
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=FakePageFetcher(
            {approved: FetchedPage(final_url=approved, text="usable evidence")}
        ),
    )

    results = searcher.search(SearchPlan(queries=["dog concern veterinary"]))

    assert [item.title for item in results] == ["Recovered"]
    assert client.queries[0] == client.queries[1]


def test_all_provider_failures_stop_after_one_retry() -> None:
    client = SequencedSearchClient(
        [TimeoutError("first failure"), TimeoutError("second failure")]
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=FakePageFetcher({}),
    )

    with pytest.raises(ModelOutputError) as raised:
        searcher.search(SearchPlan(queries=["dog concern veterinary"]))

    assert raised.value.reason == "search_failed"
    assert len(client.queries) == 2


def test_empty_provider_results_have_a_distinct_named_outcome() -> None:
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=FakeSearchClient([]),
        page_fetcher=FakePageFetcher({}),
    )

    with pytest.raises(ModelOutputError) as raised:
        searcher.search(SearchPlan(queries=["dog concern veterinary"]))

    assert raised.value.reason == "no_search_results"
    assert raised.value.stage == "approved_source_search"


def test_no_usable_approved_result_is_a_named_failure() -> None:
    client = FakeSearchClient(
        [{"title": "Off list", "href": "https://example.com", "body": "No"}]
    )
    searcher = ApprovedSourceSearcher(
        ApprovedSourceCatalog.load(DEFAULT_SOURCE_CATALOG_PATH),
        search_client=client,
        page_fetcher=FakePageFetcher({}),
    )

    with pytest.raises(ModelOutputError) as raised:
        searcher.search(SearchPlan(queries=["dog concern veterinary"]))

    assert raised.value.reason == "insufficient_evidence"
    assert raised.value.stage == "approved_source_search"


def test_source_catalog_path_is_inside_the_project() -> None:
    assert Path(DEFAULT_SOURCE_CATALOG_PATH).name == "approved_sources.toml"
