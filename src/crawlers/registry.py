"""Crawler registry and integration helpers."""

from __future__ import annotations

from pathlib import Path

from src.crawlers.base import BlogCrawler, PaperCrawler
from src.crawlers.ccs_crawler import CCSCrawler
from src.crawlers.cloudflare_blog_crawler import CloudflareSecurityCrawler
from src.crawlers.ndss_crawler import NDSSCrawler
from src.crawlers.portswigger_crawler import PortSwiggerResearchCrawler
from src.crawlers.project_zero_crawler import ProjectZeroCrawler
from src.crawlers.sp_crawler import SPCrawler
from src.crawlers.usenix_security_crawler import USENIXSecurityCrawler

PAPER_CRAWLER_REGISTRY: dict[str, type[PaperCrawler]] = {
    "ndss": NDSSCrawler,
    "sp": SPCrawler,
    "ccs": CCSCrawler,
    "usenix-security": USENIXSecurityCrawler,
}

BLOG_CRAWLER_REGISTRY: dict[str, type[BlogCrawler]] = {
    "portswigger": PortSwiggerResearchCrawler,
    "project-zero": ProjectZeroCrawler,
    "cloudflare-security": CloudflareSecurityCrawler,
}


def build_default_paper_crawlers() -> dict[str, PaperCrawler]:
    """Instantiate all default conference paper crawlers."""

    return {name: crawler_cls() for name, crawler_cls in PAPER_CRAWLER_REGISTRY.items()}


def build_default_blog_crawlers() -> dict[str, BlogCrawler]:
    """Instantiate all default blog crawlers."""

    return {name: crawler_cls() for name, crawler_cls in BLOG_CRAWLER_REGISTRY.items()}


def crawl_default_papers(
    years: list[int],
    *,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Run all default paper crawlers and save raw outputs."""

    target_dir = output_dir or Path("data/raw/papers")
    saved_files: dict[str, Path] = {}
    for name, crawler in build_default_paper_crawlers().items():
        papers = crawler.fetch_papers(years)
        saved_files[name] = crawler.save_raw(papers, target_dir, metadata={"years": years})
    return saved_files


def crawl_default_blogs(
    limit: int = 20,
    *,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Run all default blog crawlers and save raw outputs."""

    target_dir = output_dir or Path("data/raw/blogs")
    saved_files: dict[str, Path] = {}
    for name, crawler in build_default_blog_crawlers().items():
        articles = crawler.fetch_articles(limit=limit)
        saved_files[name] = crawler.save_raw(articles, target_dir, metadata={"limit": limit})
    return saved_files
