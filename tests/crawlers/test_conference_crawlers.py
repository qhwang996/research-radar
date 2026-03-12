"""Tests for conference crawler parsers."""

from __future__ import annotations

from src.exceptions import CrawlerError
from src.crawlers.ccs_crawler import CCSCrawler
from src.crawlers.ndss_crawler import NDSSCrawler
from src.crawlers.sp_crawler import SPCrawler
from src.crawlers.usenix_security_crawler import USENIXSecurityCrawler


def test_ndss_parser_extracts_title_authors_and_url() -> None:
    """NDSS parser should extract papers plus abstract from detail pages."""

    html = """
    <div class="pt-cv-content-item">
      <h2 class="pt-cv-title">
        <a href="/ndss-paper/example-paper/">Example NDSS Paper</a>
      </h2>
      <div class="pt-cv-ctf-value">
        <p>Alice Example (University A), Bob Example (University B)</p>
      </div>
    </div>
    """
    crawler = NDSSCrawler()
    crawler.detail_request_delay_seconds = 0.0
    crawler.fetch_url = lambda url: """
    <div class="entry-content">
      <p>Abstract: This NDSS paper studies browser isolation in depth.</p>
    </div>
    """

    papers = crawler.parse_year_page(
        html,
        year=2025,
        source_url="https://www.ndss-symposium.org/ndss2025/accepted-papers/",
    )

    assert len(papers) == 1
    assert papers[0]["title"] == "Example NDSS Paper"
    assert papers[0]["authors"] == [
        "Alice Example (University A)",
        "Bob Example (University B)",
    ]
    assert papers[0]["paper_url"] == "https://www.ndss-symposium.org/ndss-paper/example-paper/"
    assert papers[0]["abstract"] == "This NDSS paper studies browser isolation in depth."


def test_ndss_parser_keeps_abstract_none_when_detail_fetch_fails() -> None:
    """NDSS parser should not fail the whole page when one detail request fails."""

    html = """
    <div class="pt-cv-content-item">
      <h2 class="pt-cv-title">
        <a href="/ndss-paper/first-paper/">First NDSS Paper</a>
      </h2>
      <div class="pt-cv-ctf-value"><p>Alice Example</p></div>
    </div>
    <div class="pt-cv-content-item">
      <h2 class="pt-cv-title">
        <a href="/ndss-paper/second-paper/">Second NDSS Paper</a>
      </h2>
      <div class="pt-cv-ctf-value"><p>Bob Example</p></div>
    </div>
    """
    crawler = NDSSCrawler()
    crawler.detail_request_delay_seconds = 0.0

    def fetch_url(url: str) -> str:
        if url.endswith("/first-paper/"):
            raise CrawlerError("detail page failed")
        return """
        <div class="paper-data">
          <p>Abstract: This NDSS paper has a valid abstract.</p>
        </div>
        """

    crawler.fetch_url = fetch_url

    papers = crawler.parse_year_page(
        html,
        year=2025,
        source_url="https://www.ndss-symposium.org/ndss2025/accepted-papers/",
    )

    assert len(papers) == 2
    assert papers[0]["abstract"] is None
    assert papers[1]["abstract"] == "This NDSS paper has a valid abstract."


def test_sp_parser_extracts_title_authors_and_cycle() -> None:
    """IEEE S&P parser should extract cycle-specific papers."""

    html = """
    <div class="tab-pane active" id="cycle1">
      <div class="list-group-item">
        <a data-toggle="collapse" href="#collapse-0">Cycle One S&P Paper ☰</a>
        <div class="collapse authorlist" id="collapse-0">Alice Smith, Bob Jones</div>
      </div>
    </div>
    """
    crawler = SPCrawler()

    papers = crawler.parse_year_page(
        html,
        year=2026,
        source_url="https://sp2026.ieee-security.org/accepted-papers.html",
    )

    assert len(papers) == 1
    assert papers[0]["title"] == "Cycle One S&P Paper"
    assert papers[0]["authors"] == ["Alice Smith", "Bob Jones"]
    assert papers[0]["cycle"] == "cycle1"


def test_ccs_fallback_parser_extracts_titles_from_dblp() -> None:
    """CCS fallback should parse DBLP proceedings entries."""

    html = """
    <ul class="publ-list">
      <li class="entry inproceedings">
        <cite>
          <span itemprop="author"><span itemprop="name">Alice Example</span></span>
          <span itemprop="author"><span itemprop="name">Bob Example</span></span>
          <span class="title">An Example CCS Paper</span>
        </cite>
        <nav class="publ">
          <a href="https://doi.org/10.1145/example">DOI</a>
        </nav>
      </li>
    </ul>
    """
    crawler = CCSCrawler()

    papers = crawler.parse_dblp_page(
        html,
        year=2025,
        source_url="https://dblp.org/db/conf/ccs/ccs2025.html",
    )

    assert len(papers) == 1
    assert papers[0]["title"] == "An Example CCS Paper"
    assert papers[0]["authors"] == ["Alice Example", "Bob Example"]
    assert papers[0]["paper_url"] == "https://doi.org/10.1145/example"


def test_ccs_official_parser_filters_workshop_poster_demo_and_keeps_sok() -> None:
    """Official CCS parser should keep only full papers and SoK entries."""

    html = """
    <main>
      <li><a href="/paper/workshop">Workshop on Browser Security</a></li>
      <li><a href="/paper/poster">Poster: Browser Isolation Demo Board</a></li>
      <li><a href="/paper/demo">Demo: Runtime Detection for Web Attacks</a></li>
      <li><a href="/paper/sok">SoK: Web Security Measurement</a></li>
      <li><a href="/paper/full">Server-Side Taint Analysis for Web Applications</a></li>
    </main>
    """
    crawler = CCSCrawler()

    papers = crawler.parse_official_page(
        html,
        year=2025,
        source_url="https://www.sigsac.org/ccs/CCS2025/accepted-papers/",
    )

    assert [paper["title"] for paper in papers] == [
        "SoK: Web Security Measurement",
        "Server-Side Taint Analysis for Web Applications",
    ]


def test_ccs_dblp_parser_filters_non_paper_titles_and_keeps_sok() -> None:
    """DBLP fallback should exclude workshop/poster/demo-style titles but keep SoK papers."""

    html = """
    <ul class="publ-list">
      <li class="entry inproceedings">
        <cite><span class="title">The 20th Workshop on Web Defenses</span></cite>
      </li>
      <li class="entry inproceedings">
        <cite><span class="title">Tutorial: Exploit Mitigation in Practice</span></cite>
      </li>
      <li class="entry inproceedings">
        <cite><span class="title">SoK: Java Deserialization Security</span></cite>
      </li>
      <li class="entry inproceedings">
        <cite><span class="title">Finding SSRF in Modern Service Meshes</span></cite>
      </li>
    </ul>
    """
    crawler = CCSCrawler()

    papers = crawler.parse_dblp_page(
        html,
        year=2025,
        source_url="https://dblp.org/db/conf/ccs/ccs2025.html",
    )

    assert [paper["title"] for paper in papers] == [
        "SoK: Java Deserialization Security",
        "Finding SSRF in Modern Service Meshes",
    ]


def test_ccs_fetch_papers_falls_back_when_official_page_fetch_fails() -> None:
    """CCS crawler should keep going when the official page returns an HTTP error."""

    crawler = CCSCrawler()

    def fetch_url(url: str) -> str:
        if "sigsac.org" in url:
            raise CrawlerError("official page failed")
        return """
        <ul class="publ-list">
          <li class="entry inproceedings">
            <cite>
              <span itemprop="author"><span itemprop="name">Alice Example</span></span>
              <span class="title">Recovered CCS Paper</span>
            </cite>
            <nav class="publ">
              <a href="https://doi.org/10.1145/recovered">DOI</a>
            </nav>
          </li>
        </ul>
        """

    crawler.fetch_url = fetch_url

    papers = crawler.fetch_papers([2023])

    assert len(papers) == 1
    assert papers[0]["title"] == "Recovered CCS Paper"
    assert papers[0]["authors"] == ["Alice Example"]
    assert papers[0]["paper_url"] == "https://doi.org/10.1145/recovered"


def test_usenix_parser_extracts_paper_and_authors() -> None:
    """USENIX parser should extract papers and detail-page abstracts."""

    html = """
    <div class="views-row">
      <h2><a href="/conference/usenixsecurity25/presentation/example-paper">USENIX Security Paper</a></h2>
      <div class="field field-name-field-paper-presenters">
        <div class="field-item">Maya Example, Nick Example</div>
      </div>
    </div>
    """
    crawler = USENIXSecurityCrawler()
    crawler.detail_request_delay_seconds = 0.0
    crawler.fetch_url = lambda url: """
    <div class="field field-name-field-paper-description field-type-text-long field-label-hidden">
      Abstract: A detailed analysis of browser isolation in production.
    </div>
    """

    papers = crawler.parse_technical_sessions_page(
        html,
        year=2025,
        source_url="https://www.usenix.org/conference/usenixsecurity25/technical-sessions",
    )

    assert len(papers) == 1
    assert papers[0]["title"] == "USENIX Security Paper"
    assert papers[0]["authors"] == ["Maya Example", "Nick Example"]
    assert (
        papers[0]["paper_url"]
        == "https://www.usenix.org/conference/usenixsecurity25/presentation/example-paper"
    )
    assert papers[0]["abstract"] == "A detailed analysis of browser isolation in production."


def test_usenix_extract_abstract_from_primary_selector() -> None:
    """USENIX abstract extraction should match the primary detail-page selector."""

    html = """
    <div class="field field-name-field-paper-description field-type-text-long field-label-hidden">
      Abstract: An end-to-end study of server-side vulnerability discovery.
    </div>
    """
    crawler = USENIXSecurityCrawler()

    abstract = crawler._extract_abstract(html)

    assert abstract == "An end-to-end study of server-side vulnerability discovery."


def test_usenix_parser_keeps_abstract_none_when_detail_fetch_fails() -> None:
    """USENIX parser should continue when one detail page request fails."""

    html = """
    <div class="views-row">
      <h2><a href="/conference/usenixsecurity25/presentation/first-paper">First Paper</a></h2>
      <div class="field field-name-field-paper-presenters">
        <div class="field-item">Alice Example</div>
      </div>
    </div>
    <div class="views-row">
      <h2><a href="/conference/usenixsecurity25/presentation/second-paper">Second Paper</a></h2>
      <div class="field field-name-field-paper-presenters">
        <div class="field-item">Bob Example</div>
      </div>
    </div>
    """
    crawler = USENIXSecurityCrawler()
    crawler.detail_request_delay_seconds = 0.0

    def fetch_url(url: str) -> str:
        if url.endswith("/first-paper"):
            raise CrawlerError("detail page failed")
        return """
        <div class="paragraph-text-full">
          Abstract: This USENIX paper includes a recovered abstract.
        </div>
        """

    crawler.fetch_url = fetch_url

    papers = crawler.parse_technical_sessions_page(
        html,
        year=2025,
        source_url="https://www.usenix.org/conference/usenixsecurity25/technical-sessions",
    )

    assert len(papers) == 2
    assert papers[0]["abstract"] is None
    assert papers[1]["abstract"] == "This USENIX paper includes a recovered abstract."
