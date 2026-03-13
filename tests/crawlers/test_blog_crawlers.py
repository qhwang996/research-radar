"""Tests for blog crawler parsers."""

from __future__ import annotations

from src.crawlers.cloudflare_blog_crawler import CloudflareSecurityCrawler
from src.crawlers.portswigger_crawler import PortSwiggerResearchCrawler
from src.crawlers.project_zero_crawler import ProjectZeroCrawler


def test_portswigger_parser_extracts_article_cards() -> None:
    """PortSwigger HTML fallback should extract noscript article cards."""

    html = """
    <div class="noscript-postlist">
      <a href="/research/example-desync" class="noscript-post">
        <span class="main">HTTP desync attacks: Example edition</span>
        <span class="sub">06 March 2026 at 13:15 UTC</span>
      </a>
    </div>
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
    assert articles[0]["excerpt"] is None


def test_portswigger_rss_parser_extracts_recent_items() -> None:
    """PortSwigger RSS parsing should extract stable title, date, and excerpt."""

    xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title><![CDATA[Top 10 web hacking techniques of 2025]]></title>
          <description><![CDATA[Community-powered must-read web security research.]]></description>
          <pubDate>Thu, 05 Feb 2026 15:28:08 GMT</pubDate>
          <link>https://portswigger.net/research/top-10-web-hacking-techniques-of-2025</link>
        </item>
      </channel>
    </rss>
    """
    crawler = PortSwiggerResearchCrawler()

    articles = crawler.parse_rss_feed(
        xml,
        source_url="https://portswigger.net/research/articles",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Top 10 web hacking techniques of 2025"
    assert articles[0]["published_at"] == "2026-02-05"
    assert articles[0]["excerpt"] == "Community-powered must-read web security research."


def test_project_zero_parser_extracts_author_date_and_excerpt_from_current_site() -> None:
    """Project Zero parser should extract metadata from the current site structure."""

    html = """
    <article class="grid">
      <div class="post-title">
        <a href="/2026/03/example.html">Example Zero-Day Post</a>
      </div>
      <div class="post-meta">
        <a class="post-date" href="/2026/03/example.html">2026-Mar-03</a>
        <span class="post-author">Alice Zero</span>
      </div>
      <section class="post-content-snippet">
        <p>Details about a memory corruption bug.</p>
      </section>
    </article>
    """
    crawler = ProjectZeroCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://projectzero.google/",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Example Zero-Day Post"
    assert articles[0]["authors"] == ["Alice Zero"]
    assert articles[0]["published_at"] == "2026-03-03"
    assert articles[0]["excerpt"] == "Details about a memory corruption bug."
    assert articles[0]["article_url"] == "https://projectzero.google/2026/03/example.html"


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
        source_url="https://projectzero.google/",
    )

    assert len(articles) == 1
    assert articles[0]["published_at"] == "2026-03-01"


def test_project_zero_parser_rewrites_old_blogspot_article_urls_to_new_host() -> None:
    """Project Zero parser should normalize article URLs onto projectzero.google."""

    html = """
    <article class="grid">
      <div class="post-title">
        <a href="https://googleprojectzero.blogspot.com/2026/03/example.html">Example Zero-Day Post</a>
      </div>
      <div class="post-meta">
        <a class="post-date" href="https://googleprojectzero.blogspot.com/2026/03/example.html">2026-Mar-03</a>
        <span class="post-author">Alice Zero</span>
      </div>
      <section class="post-content-snippet">
        <p>Details about a memory corruption bug.</p>
      </section>
    </article>
    """
    crawler = ProjectZeroCrawler()

    articles = crawler.parse_articles_page(
        html,
        source_url="https://projectzero.google/",
    )

    assert len(articles) == 1
    assert articles[0]["article_url"] == "https://projectzero.google/2026/03/example.html"


def test_cloudflare_parser_extracts_security_posts() -> None:
    """Cloudflare parser should extract security-tagged blog cards."""

    html = """
    <article class="w-50-l mt4 mt2-l mb4 ph3 bb b--gray8 bn-l">
      <div class="w-100">
        <a class="fw5 no-underline gray1" data-testid="post-title" href="/the-latest/example-security-post/">
          <h2 class="fw5 mt2">The latest on Web isolation</h2>
        </a>
        <p class="f3 fw5 gray5 my" data-testid="post-date">2026-02-20</p>
        <div>
          <a data-testid="post-tag" href="/tag/security/">Security</a>
          <a data-testid="post-tag" href="/tag/browser/">Browser</a>
        </div>
        <p class="f3 fw4 gray1 lh-copy" data-testid="post-content">A deep dive into browser isolation.</p>
        <ul class="author-lists flex pl0">
          <li><div class="author-name-tooltip"><a href="/author/cloudflare-research/">Cloudflare Research</a></div></li>
        </ul>
      </div>
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
    assert articles[0]["excerpt"] == "A deep dive into browser isolation."
    assert articles[0]["tags"] == ["Security", "Browser"]


def test_cloudflare_parser_supports_current_relative_post_links() -> None:
    """Cloudflare parser should also accept current more-posts article cards."""

    html = """
    <article class="w-100 w-100-m ph3 mb4" data-testid="more-posts-article">
      <p class="f3 fw5 gray1" data-iso-date="2026-03-03T14:00+08:00">March 03, 2026 6:00 AM</p>
      <a class="no-underline gray1 f4 fw5" href="/email-security-phishing-gap-llm/">
        <h6 class="gray1 f4 fw5 mt2">From reactive to proactive</h6>
      </a>
      <p class="gray1 lh-copy">LLM-assisted phishing defense overview.</p>
      <ul class="flex pl0 fw6 f2">
        <li class="list flex items-center">
          <div class="author-name-tooltip"><a class="fw5 f2 black no-underline" href="/author/sebastian-alovisi/">Sebastian Alovisi</a></div>
        </li>
      </ul>
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
    assert articles[0]["published_at"] == "2026-03-03"
    assert articles[0]["excerpt"] == "LLM-assisted phishing defense overview."
