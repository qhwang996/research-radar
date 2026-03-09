"""Cloudflare security blog crawler."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text


class CloudflareSecurityCrawler(BlogCrawler):
    """Crawler for Cloudflare security-tagged blog posts."""

    source_name = "Cloudflare Security Blog"
    source_slug = "cloudflare_security"
    listing_url = "https://blog.cloudflare.com/tag/security/"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent Cloudflare security blog posts."""

        html = self.fetch_url(self.listing_url)
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the Cloudflare security tag page."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for container in soup.select("article, li, div"):
            title_node = container.select_one("h2 a[href], h3 a[href], a[href]")
            if not title_node:
                continue

            article_url = self.to_absolute_url(source_url, title_node.get("href"))
            title = clean_text(title_node.get_text(" ", strip=True))
            if not article_url or article_url in seen_urls or len(title) < 12:
                continue
            if "/tag/" in article_url or "/search/" in article_url:
                continue

            time_node = container.select_one("time[datetime], time")
            author_node = container.select_one("[rel='author'], .author, .Card-author")
            excerpt_node = container.find("p")

            published_at = None
            if time_node:
                published_at = clean_text(time_node.get("datetime")) or clean_text(time_node.get_text(" ", strip=True))
            if not published_at:
                href = title_node.get("href", "")
                match = re.search(r"/(\d{4})/(\d{2})/", href)
                if match:
                    published_at = f"{match.group(1)}-{match.group(2)}-01"

            authors = []
            if author_node:
                author_text = clean_text(author_node.get_text(" ", strip=True))
                if author_text:
                    authors = [author_text]

            articles.append(
                {
                    "title": title,
                    "authors": authors,
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": article_url,
                    "excerpt": clean_text(excerpt_node.get_text(" ", strip=True)) if excerpt_node else None,
                    "tags": ["security"],
                    "source_type": "blogs",
                }
            )
            seen_urls.add(article_url)

        return articles
