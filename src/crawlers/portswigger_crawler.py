"""PortSwigger Research blog crawler."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text, parse_date_to_iso
from src.exceptions import CrawlerError

logger = logging.getLogger(__name__)


class PortSwiggerResearchCrawler(BlogCrawler):
    """Crawler for PortSwigger Research articles."""

    source_name = "PortSwigger Research"
    source_slug = "portswigger_research"
    listing_url = "https://portswigger.net/research/articles"
    rss_url = "https://portswigger.net/research/rss"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent PortSwigger Research articles."""

        try:
            feed = self.fetch_url(self.rss_url)
            articles = self.parse_rss_feed(feed, source_url=self.listing_url)
            if articles:
                return articles[:limit]
        except CrawlerError:
            logger.warning("Falling back to HTML parsing for %s", self.source_name)

        html = self.fetch_url(self.listing_url)
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the PortSwigger research listing page fallback."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for link in soup.select("a.noscript-post[href]"):
            article_url = self.to_absolute_url(source_url, link.get("href"))
            title = clean_text(link.select_one(".main").get_text(" ", strip=True) if link.select_one(".main") else "")
            title = title.rstrip(":").strip()
            if not article_url or article_url in seen_urls:
                continue
            if len(title) < 12:
                continue

            date_text = clean_text(link.select_one(".sub").get_text(" ", strip=True) if link.select_one(".sub") else "")
            published_at = parse_date_to_iso(
                date_text,
                ["%d %B %Y at %H:%M %Z", "%d %B %Y", "%d %b %Y"],
            )

            articles.append(
                {
                    "title": title,
                    "authors": [],
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": article_url,
                    "excerpt": None,
                    "tags": [],
                    "source_type": "blogs",
                }
            )
            seen_urls.add(article_url)

        return articles

    def parse_rss_feed(self, xml: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the PortSwigger RSS feed for stable article metadata."""

        soup = BeautifulSoup(xml, "xml")
        articles: list[dict[str, Any]] = []

        for item in soup.find_all("item"):
            title = clean_text(item.title.get_text(" ", strip=True) if item.title else "")
            article_url = clean_text(item.link.get_text(" ", strip=True) if item.link else "")
            excerpt = clean_text(item.description.get_text(" ", strip=True) if item.description else "") or None
            published_at = parse_date_to_iso(
                item.pubDate.get_text(" ", strip=True) if item.pubDate else None,
                ["%a, %d %b %Y %H:%M:%S %Z"],
            )
            if not article_url or len(title) < 12:
                continue

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

        return articles
