"""Cloudflare security blog crawler."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from src.crawlers.base import BlogCrawler, clean_text, parse_date_to_iso


class CloudflareSecurityCrawler(BlogCrawler):
    """Crawler for Cloudflare security-tagged blog posts."""

    source_name = "Cloudflare Security Blog"
    source_slug = "cloudflare_security"
    listing_url = "https://blog.cloudflare.com/tag/security/"

    def fetch_articles(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent Cloudflare security blog posts."""

        response = self.fetch_response(self.listing_url)
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        html = response.text
        articles = self.parse_articles_page(html, source_url=self.listing_url)
        return articles[:limit]

    def parse_articles_page(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Parse the Cloudflare security tag page."""

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for container in soup.select("article"):
            title_node = container.select_one(
                "a[data-testid='post-title'][href], a.no-underline.gray1.f4.fw5[href], h2 a[href], h3 a[href], h6 a[href]"
            )
            if not title_node:
                continue

            article_url = self.to_absolute_url(source_url, title_node.get("href"))
            title = clean_text(title_node.get_text(" ", strip=True))
            if not article_url or article_url in seen_urls or len(title) < 12:
                continue
            if "/tag/" in article_url or "/search/" in article_url or "/author/" in article_url:
                continue

            time_node = container.select_one("[data-testid='post-date'], [data-iso-date], time[datetime], time")
            excerpt_node = container.select_one("[data-testid='post-content'], p.gray1.lh-copy, p.f3.fw4.gray1.lh-copy, p.f4.fw3.lh-copy")

            published_at = None
            if time_node:
                published_at = clean_text(time_node.get("data-iso-date")) or clean_text(time_node.get("datetime"))
                if published_at and re.match(r"\d{4}-\d{2}-\d{2}", published_at):
                    published_at = published_at[:10]
                else:
                    published_at = parse_date_to_iso(
                        published_at or clean_text(time_node.get_text(" ", strip=True)),
                        ["%Y-%m-%d", "%B %d, %Y %I:%M %p"],
                    )
            if not published_at:
                href = title_node.get("href", "")
                match = re.search(r"/(\d{4})/(\d{2})/", href)
                if match:
                    published_at = f"{match.group(1)}-{match.group(2)}-01"

            authors: list[str] = []
            for author_link in container.select("ul.author-lists a[href*='/author/'], [rel='author'][href], .author-name-tooltip a[href*='/author/']"):
                author_text = clean_text(author_link.get_text(" ", strip=True))
                if author_text and author_text not in authors:
                    authors.append(author_text)

            tags: list[str] = []
            for tag_link in container.select("a[href*='/tag/']"):
                tag = clean_text(tag_link.get_text(" ", strip=True))
                if tag and tag not in tags:
                    tags.append(tag)

            articles.append(
                {
                    "title": title,
                    "authors": authors,
                    "published_at": published_at,
                    "source_url": source_url,
                    "article_url": article_url,
                    "excerpt": clean_text(excerpt_node.get_text(" ", strip=True)) if excerpt_node else None,
                    "tags": tags or ["security"],
                    "source_type": "blogs",
                }
            )
            seen_urls.add(article_url)

        return articles
