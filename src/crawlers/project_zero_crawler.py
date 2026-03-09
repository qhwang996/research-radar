"""Google Project Zero blog crawler."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text, parse_date_to_iso


class ProjectZeroCrawler(BlogCrawler):
    """Crawler for the Google Project Zero blog."""

    source_name = "Google Project Zero"
    source_slug = "project_zero"
    listing_url = "https://googleprojectzero.blogspot.com/"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent Project Zero posts."""

        html = self.fetch_url(self.listing_url)
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the Project Zero blog landing page."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []

        for post in soup.select(".post-outer, .date-posts .post, article.grid"):
            title_node = post.select_one("h3.post-title a, .post-title a")
            if not title_node:
                continue

            title = clean_text(title_node.get_text(" ", strip=True))
            if not title:
                continue

            date_text = ""
            date_node = post.select_one("h2.date-header span, h2.date-header, time")
            if date_node:
                date_text = clean_text(date_node.get_text(" ", strip=True))

            if not date_text:
                href = title_node.get("href", "")
                match = re.search(r"/(\d{4})/(\d{2})/", href)
                if match:
                    date_text = f"{match.group(1)}-{match.group(2)}-01"

            author_text = clean_text(
                post.select_one(".post-author .fn, .post-header-line-1 .fn, .fn").get_text(" ", strip=True)
                if post.select_one(".post-author .fn, .post-header-line-1 .fn, .fn")
                else ""
            )
            excerpt_node = post.select_one(".post-body")

            published_at = parse_date_to_iso(date_text, ["%A, %B %d, %Y"])
            if not published_at and re.match(r"\d{4}-\d{2}-\d{2}", date_text):
                published_at = date_text

            articles.append(
                {
                    "title": title,
                    "authors": [author_text] if author_text else [],
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": self.to_absolute_url(source_url, title_node.get("href")),
                    "excerpt": clean_text(excerpt_node.get_text(" ", strip=True)) if excerpt_node else None,
                    "tags": [],
                    "source_type": "blogs",
                }
            )

        return articles
