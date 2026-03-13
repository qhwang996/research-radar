"""Google Project Zero blog crawler."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text, parse_date_to_iso, split_authors


class ProjectZeroCrawler(BlogCrawler):
    """Crawler for the Google Project Zero blog."""

    source_name = "Google Project Zero"
    source_slug = "project_zero"
    listing_url = "https://projectzero.google/"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent Project Zero posts."""

        response = self.fetch_response(self.listing_url)
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        html = response.text
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the Project Zero blog landing page."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []

        for post in soup.select("article.grid, .post-outer, .date-posts .post"):
            title_node = post.select_one(".post-title > a, h3.post-title a, .post-title a")
            if not title_node:
                continue

            title = clean_text(title_node.get_text(" ", strip=True))
            if not title:
                continue

            date_text = ""
            date_node = post.select_one(".post-meta .post-date, .post-date, h2.date-header span, h2.date-header, time")
            if date_node:
                date_text = clean_text(date_node.get_text(" ", strip=True))

            published_at = parse_date_to_iso(date_text, ["%Y-%b-%d", "%A, %B %d, %Y"])
            if not date_text:
                href = title_node.get("href", "")
                match = re.search(r"/(\d{4})/(\d{2})/", href)
                if match:
                    date_text = f"{match.group(1)}-{match.group(2)}-01"
                    published_at = date_text

            if not published_at and re.match(r"\d{4}-\d{2}-\d{2}", date_text):
                published_at = date_text

            author_node = post.select_one(".post-meta .post-author, .post-author, .post-author .fn, .post-header-line-1 .fn, .fn")
            author_text = clean_text(author_node.get_text(" ", strip=True) if author_node else "")
            excerpt_node = post.select_one("section.post-content-snippet p, .post-content-snippet p, .post-body p, .post-body")

            articles.append(
                {
                    "title": title,
                    "authors": split_authors(author_text),
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": self._normalize_article_url(source_url, title_node.get("href")),
                    "excerpt": clean_text(excerpt_node.get_text(" ", strip=True)) if excerpt_node else None,
                    "tags": [],
                    "source_type": "blogs",
                }
            )

        return articles

    def _normalize_article_url(self, source_url: str, href: str | None) -> str | None:
        """Normalize article URLs onto the current Project Zero site host."""

        article_url = self.to_absolute_url(source_url, href)
        if not article_url:
            return None

        source_parts = urlparse(source_url)
        article_parts = urlparse(article_url)
        if article_parts.netloc.lower() == source_parts.netloc.lower():
            return article_url
        if not article_parts.path.startswith("/20"):
            return article_url

        return urlunparse(
            article_parts._replace(
                scheme=source_parts.scheme or article_parts.scheme,
                netloc=source_parts.netloc or article_parts.netloc,
            )
        )
