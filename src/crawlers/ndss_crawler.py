"""NDSS conference paper crawler."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import PaperCrawler, clean_text, split_authors

logger = logging.getLogger(__name__)


class NDSSCrawler(PaperCrawler):
    """Crawler for NDSS accepted papers."""

    source_name = "NDSS"
    source_slug = "ndss"

    def build_year_url(self, year: int) -> str:
        """Return the accepted papers URL for an NDSS year."""

        return f"https://www.ndss-symposium.org/ndss{year}/accepted-papers/"

    def fetch_papers(self, years: list[int]) -> list[dict[str, Any]]:
        """Fetch accepted papers across one or more NDSS years."""

        papers: list[dict[str, Any]] = []
        for year in self.normalize_years(years):
            year_url = self.build_year_url(year)
            html = self.fetch_url(year_url)
            year_papers = self.parse_year_page(html, year=year, source_url=year_url)
            logger.info("Fetched %s NDSS papers for %s", len(year_papers), year)
            papers.extend(year_papers)
        return papers

    def parse_year_page(
        self,
        html: str,
        *,
        year: int,
        source_url: str,
    ) -> list[dict[str, Any]]:
        """Parse an NDSS accepted papers page into normalized paper records."""

        soup = BeautifulSoup(html, "html.parser")
        papers: list[dict[str, Any]] = []
        for entry in soup.select("div.pt-cv-content-item"):
            title_link = entry.select_one("h2.pt-cv-title a")
            title_node = title_link or entry.select_one("h2.pt-cv-title")
            if title_node is None:
                continue

            title = clean_text(title_node.get_text(" ", strip=True))
            if not title:
                continue

            author_node = entry.select_one("div.pt-cv-ctf-value p")
            author_text = clean_text(author_node.get_text(" ", strip=True)) if author_node else ""
            authors = split_authors(author_text)

            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "conference": f"NDSS {year}",
                    "source_url": source_url,
                    "paper_url": self.to_absolute_url(
                        source_url,
                        title_link.get("href") if title_link else None,
                    ),
                    "abstract": None,
                    "pdf_url": None,
                    "data_completeness": "with_authors" if authors else "title_only",
                    "source_type": "papers",
                }
            )

        return papers
