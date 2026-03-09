"""Tests for blog crawler parsers."""

from __future__ import annotations

from src.crawlers.cloudflare_blog_crawler import CloudflareSecurityCrawler
from src.crawlers.portswigger_crawler import PortSwiggerResearchCrawler
from src.crawlers.project_zero_crawler import ProjectZeroCrawler


def test_portswigger_parser_extracts_article_cards() -> None:
    """PortSwigger parser should extract article metadata from listing links."""

    html = """
    <article>
      <a href="/research/example-desync">HTTP desync attacks: Example edition</a>
      <span>06 Mar 2026</span>
      <p>New exploitation technique summary.</p>
    </article>
    """
    crawler = PortSwiggerResearchCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://portswigger.net/research/articles",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "HTTP desync attacks: Example edition"
    assert articles[0]["published_at"] == "2026-03-06"
    assert articles[0]["article_url"] == "https://portswigger.net/research/example-desync"


def test_project_zero_parser_extracts_author_and_date() -> None:
    """Project Zero parser should extract standard Blogger post metadata."""

    html = """
    <div class="post-outer">
      <h2 class="date-header"><span>Tuesday, March 03, 2026</span></h2>
      <h3 class="post-title entry-title">
        <a href="https://googleprojectzero.blogspot.com/2026/03/example.html">Example Zero-Day Post</a>
      </h3>
      <span class="fn">Alice Zero</span>
      <div class="post-body">Details about a memory corruption bug.</div>
    </div>
    """
    crawler = ProjectZeroCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://googleprojectzero.blogspot.com/",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Example Zero-Day Post"
    assert articles[0]["authors"] == ["Alice Zero"]
    assert articles[0]["published_at"] == "2026-03-03"


def test_project_zero_parser_falls_back_to_date_from_url() -> None:
    """Project Zero parser should recover month-level dates from post URLs."""

    html = """
    <article class="grid">
      <div class="post-title">
        <a href="/2026/03/example-post.html">Fallback Date Post</a>
      </div>
    </article>
    """
    crawler = ProjectZeroCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://googleprojectzero.blogspot.com/",
    )

    assert len(articles) == 1
    assert articles[0]["published_at"] == "2026-03-01"


def test_cloudflare_parser_extracts_security_posts() -> None:
    """Cloudflare parser should extract security-tagged blog cards."""

    html = """
    <article>
      <a href="/the-latest/example-security-post/">The latest on Web isolation</a>
      <time datetime="2026-02-20">February 20, 2026</time>
      <span rel="author">Cloudflare Research</span>
      <p>A deep dive into browser isolation.</p>
    </article>
    """
    crawler = CloudflareSecurityCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://blog.cloudflare.com/tag/security/",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "The latest on Web isolation"
    assert articles[0]["authors"] == ["Cloudflare Research"]
    assert articles[0]["published_at"] == "2026-02-20"
    assert articles[0]["article_url"] == "https://blog.cloudflare.com/the-latest/example-security-post/"


def test_cloudflare_parser_supports_current_relative_post_links() -> None:
    """Cloudflare parser should also accept current non-the-latest article URLs."""

    html = """
    <article class="featured-post">
      <h2><a href="/email-security-phishing-gap-llm/">From reactive to proactive</a></h2>
      <span rel="author">Sebastian Alovisi</span>
      <p>LLM-assisted phishing defense overview.</p>
    </article>
    """
    crawler = CloudflareSecurityCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://blog.cloudflare.com/tag/security/",
    )

    assert len(articles) == 1
    assert articles[0]["article_url"] == "https://blog.cloudflare.com/email-security-phishing-gap-llm/"
    assert articles[0]["authors"] == ["Sebastian Alovisi"]
