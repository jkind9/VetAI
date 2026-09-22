"""Allowlisted web search and bounded evidence extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from backend.approved_sources import ApprovedSourceCatalog
from backend.schemas import EvidenceItem, ModelOutputError, SearchPlan

MAX_RAW_RESULTS = 12
MAX_EVIDENCE_ITEMS = 4
MAX_PAGE_BYTES = 500_000
MAX_EXCERPT_CHARS = 4000
MAX_REDIRECTS = 3

_URL = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE = re.compile(r"(?<!\w)\+?\d(?:[\s().-]*\d){8,}(?!\w)")


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    text: str


class SearchClient(Protocol):
    def text(self, query: str, **kwargs: Any) -> list[dict[str, Any]]: ...


class PageFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class DDGSSearchClient:
    """Lazy wrapper so importing the backend does not initialise a search provider."""

    def __init__(self, timeout: float) -> None:
        from ddgs import DDGS

        self._client = DDGS(timeout=max(1, int(timeout)))

    def text(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self._client.text(query, **kwargs)


class _VisibleTextParser(HTMLParser):
    _IGNORED = {"script", "style", "nav", "form", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._IGNORED:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0 and data.strip():
            self.parts.append(data.strip())


class HttpPageFetcher:
    """Fetch approved pages while validating each redirect before following it."""

    def __init__(self, catalog: ApprovedSourceCatalog, timeout: float) -> None:
        self._catalog = catalog
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": "VetAI technical-test evidence search/0.1"},
        )

    def fetch(self, url: str) -> FetchedPage:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if self._catalog.match(current) is None:
                raise ValueError("redirect target is not an approved HTTPS source")
            response = self._client.get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("redirect response did not include a target")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            if len(response.content) > MAX_PAGE_BYTES:
                raise ValueError("approved page exceeded the evidence size limit")
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                parser = _VisibleTextParser()
                parser.feed(response.text)
                text = " ".join(parser.parts)
            elif content_type.startswith("text/") or not content_type:
                text = response.text
            else:
                raise ValueError("approved result was not a text page")
            compact = " ".join(text.split())[:MAX_EXCERPT_CHARS]
            if not compact:
                raise ValueError("approved page contained no usable text")
            return FetchedPage(final_url=str(response.url), text=compact)
        raise ValueError("approved page exceeded the redirect limit")


def query_is_safe(query: str) -> bool:
    """Reject obvious contact data or URLs before any external request."""
    return not any(pattern.search(query) for pattern in (_URL, _EMAIL, _PHONE))


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


class ApprovedSourceSearcher:
    """Search inside the reviewed domain scope, then verify every returned URL again."""

    def __init__(
        self,
        catalog: ApprovedSourceCatalog,
        *,
        search_client: SearchClient,
        page_fetcher: PageFetcher,
        region: str = "uk-en",
    ) -> None:
        self._catalog = catalog
        self._search_client = search_client
        self._page_fetcher = page_fetcher
        self._region = region

    @classmethod
    def from_defaults(
        cls, *, timeout: float = 12.0, region: str = "uk-en"
    ) -> ApprovedSourceSearcher:
        catalog = ApprovedSourceCatalog.load()
        return cls(
            catalog,
            search_client=DDGSSearchClient(timeout),
            page_fetcher=HttpPageFetcher(catalog, timeout),
            region=region,
        )

    def search(self, plan: SearchPlan) -> list[EvidenceItem]:
        for query in plan.queries:
            if not query_is_safe(query):
                raise ModelOutputError(
                    "unsafe_search_query", stage="approved_source_search"
                )

        raw_results: list[dict[str, Any]] = []
        domain_filter = " OR ".join(f"site:{domain}" for domain in sorted(self._catalog.domains))
        try:
            for query in plan.queries:
                raw_results.extend(
                    self._search_client.text(
                        f"({domain_filter}) {query}",
                        region=self._region,
                        safesearch="moderate",
                        max_results=MAX_RAW_RESULTS,
                    )
                )
        except Exception as error:  # provider exceptions are intentionally hidden
            raise ModelOutputError(
                "search_failed", type(error).__name__, stage="approved_source_search"
            ) from error

        evidence: list[EvidenceItem] = []
        seen: set[str] = set()
        for raw in raw_results:
            candidate = raw.get("href") or raw.get("url")
            if not isinstance(candidate, str):
                continue
            source = self._catalog.match(candidate)
            if source is None:
                continue
            canonical = _canonical_url(candidate)
            if canonical in seen:
                continue
            seen.add(canonical)
            try:
                page = self._page_fetcher.fetch(candidate)
            except Exception:
                continue
            final_source = self._catalog.match(page.final_url)
            if final_source is None:
                continue
            title = raw.get("title")
            if not isinstance(title, str) or not title.strip():
                title = (
                    urlsplit(page.final_url).path.rsplit("/", 1)[-1]
                    or final_source.organisation
                )
            evidence.append(
                EvidenceItem(
                    source_id=f"S{len(evidence) + 1}",
                    title=title,
                    url=page.final_url,
                    organisation=final_source.organisation,
                    excerpt=page.text[:MAX_EXCERPT_CHARS],
                )
            )
            if len(evidence) >= MAX_EVIDENCE_ITEMS:
                break

        if not evidence:
            raise ModelOutputError(
                "insufficient_evidence", stage="approved_source_search"
            )
        return evidence
