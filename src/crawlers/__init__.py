"""Crawler implementations and integration helpers."""

from src.crawlers.base import BaseCrawler, BlogCrawler, PaperCrawler
from src.crawlers.ccs_crawler import CCSCrawler
from src.crawlers.cloudflare_blog_crawler import CloudflareSecurityCrawler
from src.crawlers.ndss_crawler import NDSSCrawler
from src.crawlers.portswigger_crawler import PortSwiggerResearchCrawler
from src.crawlers.project_zero_crawler import ProjectZeroCrawler
from src.crawlers.registry import (
    BLOG_CRAWLER_REGISTRY,
    PAPER_CRAWLER_REGISTRY,
    build_default_blog_crawlers,
    build_default_paper_crawlers,
    crawl_default_blogs,
    crawl_default_papers,
)
from src.crawlers.sp_crawler import SPCrawler
from src.crawlers.usenix_security_crawler import USENIXSecurityCrawler

__all__ = [
    "BaseCrawler",
    "PaperCrawler",
    "BlogCrawler",
    "NDSSCrawler",
    "SPCrawler",
    "CCSCrawler",
    "USENIXSecurityCrawler",
    "PortSwiggerResearchCrawler",
    "ProjectZeroCrawler",
    "CloudflareSecurityCrawler",
    "PAPER_CRAWLER_REGISTRY",
    "BLOG_CRAWLER_REGISTRY",
    "build_default_paper_crawlers",
    "build_default_blog_crawlers",
    "crawl_default_papers",
    "crawl_default_blogs",
]
