"""ACM CCS conference paper crawler with resilient fallbacks."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import PaperCrawler, clean_text

logger = logging.getLogger(__name__)


class CCSCrawler(PaperCrawler):
    """Crawler for ACM CCS accepted papers."""

    source_name = "ACM CCS"
    source_slug = "ccs"

    def build_official_year_url(self, year: int) -> str:
        """Return the official accepted papers page for a CCS year."""

        if year >= 2025:
            return f"https://www.sigsac.org/ccs/CCS{year}/accepted-papers/"
        return f"https://www.sigsac.org/ccs/CCS{year}/program/accepted-papers.html"

    def build_dblp_fallback_url(self, year: int) -> str:
        """Return the DBLP fallback page for a CCS year."""

        return f"https://dblp.org/db/conf/ccs/ccs{year}.html"

    def fetch_papers(self, years: list[int]) -> list[dict[str, Any]]:
        """Fetch accepted papers across one or more CCS years."""

        papers: list[dict[str, Any]] = []
        for year in self.normalize_years(years):
            official_url = self.build_official_year_url(year)
            html = self.fetch_url(official_url)
            year_papers = self.parse_official_page(html, year=year, source_url=official_url)

            if not year_papers:
                fallback_url = self.build_dblp_fallback_url(year)
                logger.warning(
                    "CCS %s official page did not expose papers in static HTML; falling back to %s",
                    year,
                    fallback_url,
                )
                fallback_html = self.fetch_url(fallback_url)
                year_papers = self.parse_dblp_page(fallback_html, year=year, source_url=fallback_url)

            logger.info("Fetched %s CCS papers for %s", len(year_papers), year)
            papers.extend(year_papers)
        return papers

    def parse_official_page(
        self,
        html: str,
        *,
        year: int,
        source_url: str,
    ) -> list[dict[str, Any]]:
        """Parse the official CCS accepted papers page if list items are present."""

        soup = BeautifulSoup(html, "html.parser")
        papers: list[dict[str, Any]] = []
        current_cycle = None

        for node in soup.select("main h2, main h3, .page_box h2, .page_box h3, main li, .page_box li"):
            if node.name in {"h2", "h3"}:
                current_cycle = clean_text(node.get_text(" ", strip=True))
                continue

            link = node.select_one("a[href]")
            if not link:
                continue

            title = clean_text(link.get_text(" ", strip=True))
            if len(title) < 10:
                continue

            papers.append(
                {
                    "title": title,
                    "authors": [],
                    "year": year,
                    "conference": f"ACM CCS {year}",
                    "source_url": source_url,
                    "paper_url": self.to_absolute_url(source_url, link.get("href")),
                    "abstract": None,
                    "pdf_url": None,
                    "cycle": current_cycle,
                    "data_completeness": "title_only",
                    "source_type": "papers",
                }
            )

        return papers

    def parse_dblp_page(
        self,
        html: str,
        *,
        year: int,
        source_url: str,
    ) -> list[dict[str, Any]]:
        """Parse the DBLP proceedings page as a fallback source."""

        soup = BeautifulSoup(html, "html.parser")
        papers: list[dict[str, Any]] = []
        for entry in soup.select("li.entry.inproceedings, li.entry.article"):
            title_node = entry.select_one("span.title")
            if not title_node:
                continue

            title = clean_text(title_node.get_text(" ", strip=True))
            if not title:
                continue

            authors: list[str] = []
            for author_node in entry.select("span[itemprop='author'] span[itemprop='name'], .authors a span, .authors a"):
                author = clean_text(author_node.get_text(" ", strip=True))
                if author and author not in authors:
                    authors.append(author)

            paper_url = None
            for link in entry.select("nav.publ a[href], ul.publ a[href], a[href]"):
                href = link.get("href")
                if not href or not href.startswith("http"):
                    continue
                if "dblp.org/rec/" in href:
                    continue
                paper_url = href
                break

            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "conference": f"ACM CCS {year}",
                    "source_url": source_url,
                    "paper_url": paper_url,
                    "abstract": None,
                    "pdf_url": None,
                    "data_completeness": "with_authors" if authors else "title_only",
                    "source_type": "papers",
                }
            )

        return papers
