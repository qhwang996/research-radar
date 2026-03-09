"""Shared crawler primitives and helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import html
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.exceptions import CrawlerError

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    )
}


def clean_text(value: str | None) -> str:
    """Normalize whitespace and HTML entities in crawler text."""

    if not value:
        return ""

    normalized = html.unescape(value)
    return re.sub(r"\s+", " ", normalized).strip()


def split_authors(author_text: str | None) -> list[str]:
    """Split author text while respecting commas inside affiliations."""

    if not author_text:
        return []

    text = clean_text(author_text)
    if not text:
        return []

    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1

        if char in {",", ";"} and depth == 0:
            candidate = clean_text("".join(current))
            if candidate:
                parts.append(candidate)
            current = []
            continue

        current.append(char)

    tail = clean_text("".join(current))
    if tail:
        parts.append(tail)

    if len(parts) == 1 and " and " in parts[0].lower():
        return [clean_text(item) for item in re.split(r"\band\b", parts[0]) if clean_text(item)]

    return parts


def parse_date_to_iso(raw_value: str | None, formats: list[str]) -> str | None:
    """Convert a date string into ISO-8601 if one format matches."""

    if not raw_value:
        return None

    candidate = clean_text(raw_value).replace(".", "")
    for fmt in formats:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class BaseCrawler(ABC):
    """Shared crawler behaviors for requests, retries, and raw storage."""

    source_name: str
    source_slug: str
    source_type: str

    def __init__(
        self,
        *,
        timeout: int = 10,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the crawler with a retry-enabled requests session."""

        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.session = self._build_session()

    def _build_session(self) -> Session:
        """Create a session with retry support for transient failures."""

        retry = Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.headers.update(self.headers)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def fetch_url(self, url: str) -> str:
        """Fetch a URL and return its response body as text."""

        logger.info("Fetching %s from %s", self.source_name, url)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s from %s: %s", self.source_name, url, exc)
            raise CrawlerError(f"Failed to fetch {self.source_name} from {url}") from exc

    def fetch_response(self, url: str) -> Response:
        """Fetch a URL and return the raw response object."""

        logger.info("Fetching response for %s from %s", self.source_name, url)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.error("Failed to fetch response for %s from %s: %s", self.source_name, url, exc)
            raise CrawlerError(f"Failed to fetch {self.source_name} from {url}") from exc

    def to_absolute_url(self, base_url: str, href: str | None) -> str | None:
        """Convert a relative href into an absolute URL."""

        if not href:
            return None
        return urljoin(base_url, href)

    def save_raw(
        self,
        items: list[dict[str, Any]],
        output_dir: Path,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Persist raw crawler output as a JSON file with metadata."""

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{self.source_slug}_{timestamp}.json"

        payload: dict[str, Any] = {
            "source": self.source_name,
            "source_slug": self.source_slug,
            "source_type": self.source_type,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_items": len(items),
            "items": items,
        }
        if self.source_type == "papers":
            payload["total_papers"] = len(items)
        if self.source_type == "blogs":
            payload["total_articles"] = len(items)
        if metadata:
            payload.update(metadata)

        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        logger.info("Saved %s items for %s to %s", len(items), self.source_name, output_path)
        return output_path


class PaperCrawler(BaseCrawler, ABC):
    """Base class for conference paper crawlers."""

    source_type = "papers"

    @abstractmethod
    def fetch_papers(self, years: list[int]) -> list[dict[str, Any]]:
        """
        Fetch paper metadata for the provided years.

        Args:
            years: Target years such as [2024, 2025, 2026].

        Returns:
            Paper dictionaries with normalized fields for downstream processing.

        Raises:
            CrawlerError: If fetching fails.
        """

    def normalize_years(self, years: list[int] | None) -> list[int]:
        """Return a de-duplicated year list while preserving input order."""

        if not years:
            return []
        return list(dict.fromkeys(years))


class BlogCrawler(BaseCrawler, ABC):
    """Base class for blog article crawlers."""

    source_type = "blogs"

    @abstractmethod
    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Fetch recent blog articles.

        Args:
            limit: Maximum number of articles to return.

        Returns:
            Blog article dictionaries with title, url, date, and optional metadata.

        Raises:
            CrawlerError: If fetching fails.
        """


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    """Return the first non-empty text match across multiple selectors."""

    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" ", strip=True))
            if value:
                return value
    return None
