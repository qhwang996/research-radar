"""IEEE S&P conference paper crawler."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import PaperCrawler, clean_text, split_authors

logger = logging.getLogger(__name__)


class SPCrawler(PaperCrawler):
    """Crawler for IEEE Symposium on Security and Privacy accepted papers."""

    source_name = "IEEE S&P"
    source_slug = "sp"

    def build_year_url(self, year: int) -> str:
        """Return the accepted papers URL for an IEEE S&P year."""

        return f"https://sp{year}.ieee-security.org/accepted-papers.html"

    def fetch_papers(self, years: list[int]) -> list[dict[str, Any]]:
        """Fetch accepted papers across one or more IEEE S&P years."""

        papers: list[dict[str, Any]] = []
        for year in self.normalize_years(years):
            year_url = self.build_year_url(year)
            html = self.fetch_url(year_url)
            year_papers = self.parse_year_page(html, year=year, source_url=year_url)
            logger.info("Fetched %s IEEE S&P papers for %s", len(year_papers), year)
            papers.extend(year_papers)
        return papers

    def parse_year_page(
        self,
        html: str,
        *,
        year: int,
        source_url: str,
    ) -> list[dict[str, Any]]:
        """Parse an IEEE S&P accepted papers page into normalized records."""

        soup = BeautifulSoup(html, "html.parser")
        papers: list[dict[str, Any]] = []
        for entry in soup.select("div.list-group-item"):
            title_node = entry.select_one("a[data-toggle='collapse']")
            if not title_node:
                continue

            title = clean_text(title_node.get_text(" ", strip=True)).replace("☰", "").strip()
            if not title:
                continue

            author_node = entry.select_one(".collapse.authorlist")
            author_text = clean_text(author_node.get_text(" ", strip=True)) if author_node else ""
            authors = split_authors(author_text)

            cycle_node = entry.find_parent(class_="tab-pane")
            cycle = cycle_node.get("id") if cycle_node else None

            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "conference": f"IEEE S&P {year}",
                    "source_url": source_url,
                    "paper_url": None,
                    "abstract": None,
                    "pdf_url": None,
                    "cycle": cycle,
                    "data_completeness": "with_authors" if authors else "title_only",
                    "source_type": "papers",
                }
            )

        return papers
