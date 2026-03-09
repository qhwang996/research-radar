"""PortSwigger Research blog crawler."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text, parse_date_to_iso

logger = logging.getLogger(__name__)


class PortSwiggerResearchCrawler(BlogCrawler):
    """Crawler for PortSwigger Research articles."""

    source_name = "PortSwigger Research"
    source_slug = "portswigger_research"
    listing_url = "https://portswigger.net/research/articles"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent PortSwigger Research articles."""

        html = self.fetch_url(self.listing_url)
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the PortSwigger research listing page."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            article_url = self.to_absolute_url(source_url, href)
            title = clean_text(link.get_text(" ", strip=True))
            if not article_url or article_url in seen_urls:
                continue
            if "/research/" not in article_url or article_url.endswith("/research/articles"):
                continue
            if len(title) < 12 or title.lower() == "view older posts":
                continue

            container = link.find_parent(["article", "li", "div", "section"])
            container_text = clean_text(container.get_text(" ", strip=True)) if container else ""
            date_match = re.search(
                r"\b\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4}\b",
                container_text,
            )
            published_at = parse_date_to_iso(
                date_match.group(0) if date_match else None,
                ["%d %B %Y", "%d %b %Y"],
            )

            excerpt = None
            if container:
                paragraph = container.find("p")
                if paragraph:
                    excerpt = clean_text(paragraph.get_text(" ", strip=True)) or None

            articles.append(
                {
                    "title": title,
                    "authors": [],
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": article_url,
                    "excerpt": excerpt,
                    "tags": [],
                    "source_type": "blogs",
                }
            )
            seen_urls.add(article_url)

        return articles
