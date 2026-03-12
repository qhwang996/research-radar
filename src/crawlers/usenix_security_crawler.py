"""USENIX Security conference paper crawler."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.crawlers.base import PaperCrawler, clean_text, split_authors

logger = logging.getLogger(__name__)


class USENIXSecurityCrawler(PaperCrawler):
    """Crawler for USENIX Security technical sessions."""

    source_name = "USENIX Security"
    source_slug = "usenix_security"
    detail_request_delay_seconds = 0.5

    def build_year_url(self, year: int) -> str:
        """Return the technical sessions page URL for a USENIX Security year."""

        return f"https://www.usenix.org/conference/usenixsecurity{year % 100:02d}/technical-sessions"

    def fetch_papers(self, years: list[int]) -> list[dict[str, Any]]:
        """Fetch papers across one or more USENIX Security years."""

        papers: list[dict[str, Any]] = []
        for year in self.normalize_years(years):
            year_url = self.build_year_url(year)
            html = self.fetch_url(year_url)
            year_papers = self.parse_technical_sessions_page(html, year=year, source_url=year_url)
            logger.info("Fetched %s USENIX Security papers for %s", len(year_papers), year)
            papers.extend(year_papers)
        return papers

    def parse_technical_sessions_page(
        self,
        html: str,
        *,
        year: int,
        source_url: str,
    ) -> list[dict[str, Any]]:
        """Parse a USENIX technical sessions page into normalized paper records."""

        soup = BeautifulSoup(html, "html.parser")
        papers: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        title_nodes = soup.select(
            "h2 a[href*='/conference/usenixsecurity'], "
            "h3 a[href*='/conference/usenixsecurity'], "
            "a[href*='/conference/usenixsecurity'][hreflang]"
        )
        for title_node in title_nodes:
            title = clean_text(title_node.get_text(" ", strip=True))
            if len(title) < 10 or title in seen_titles:
                continue

            container = self._find_paper_container(title_node)
            authors = self._extract_authors(container, title_node)
            paper_url = self.to_absolute_url(source_url, title_node.get("href"))

            paper = {
                "title": title,
                "authors": authors,
                "year": year,
                "conference": f"USENIX Security {year}",
                "source_url": source_url,
                "paper_url": paper_url,
                "abstract": self._fetch_detail_abstract(paper_url) if paper_url else None,
                "pdf_url": None,
                "data_completeness": "with_authors" if authors else "title_only",
                "source_type": "papers",
            }
            papers.append(paper)
            seen_titles.add(title)

        return papers

    def _find_paper_container(self, title_node: Tag) -> Tag:
        """Return the nearest container likely to also contain author metadata."""

        for ancestor in title_node.parents:
            if not isinstance(ancestor, Tag):
                continue
            classes = " ".join(ancestor.get("class", []))
            if any(marker in classes for marker in ["views-row", "node", "paper", "session"]):
                return ancestor
            if ancestor.name in {"article", "section", "li"}:
                return ancestor
        return title_node.parent if isinstance(title_node.parent, Tag) else title_node

    def _extract_authors(self, container: Tag, title_node: Tag) -> list[str]:
        """Extract author names from the container or nearby siblings."""

        for tag in container.find_all(["div", "p", "span"], limit=12):
            classes = " ".join(tag.get("class", []))
            if re.search(r"(author|presenter)", classes, re.IGNORECASE):
                authors = split_authors(tag.get_text(" ", strip=True))
                if authors:
                    return authors

        sibling = title_node.parent.next_sibling if isinstance(title_node.parent, Tag) else None
        while sibling is not None:
            if isinstance(sibling, Tag):
                text = clean_text(sibling.get_text(" ", strip=True))
                authors = split_authors(text)
                if len(authors) >= 2 or re.search(r"\bUniversity\b|\bInc\b|\bLab\b", text):
                    return authors
            sibling = sibling.next_sibling

        return []

    def _fetch_detail_abstract(self, paper_url: str) -> str | None:
        """Fetch one USENIX paper detail page and extract the abstract."""

        try:
            detail_html = self.fetch_url(paper_url)
            return self._extract_abstract(detail_html)
        except Exception as exc:  # pragma: no cover - exercised through parser flow tests
            logger.warning("Failed to fetch USENIX Security paper detail %s: %s", paper_url, exc)
            return None
        finally:
            self._sleep_between_detail_requests()

    def _extract_abstract(self, html: str) -> str | None:
        """Extract one abstract string from a USENIX detail page."""

        soup = BeautifulSoup(html, "html.parser")
        for selector in ["div.field-name-field-paper-description", "div.paragraph-text-full"]:
            for container in soup.select(selector):
                text = clean_text(container.get_text(" ", strip=True))
                if not text:
                    continue
                return re.sub(r"^abstract\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
        return None

    def _sleep_between_detail_requests(self) -> None:
        """Pause briefly between detail-page requests to reduce crawler pressure."""

        if self.detail_request_delay_seconds > 0:
            time.sleep(self.detail_request_delay_seconds)
