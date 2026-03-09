"""Tests for conference crawler parsers."""

from __future__ import annotations

from src.crawlers.ccs_crawler import CCSCrawler
from src.crawlers.ndss_crawler import NDSSCrawler
from src.crawlers.sp_crawler import SPCrawler
from src.crawlers.usenix_security_crawler import USENIXSecurityCrawler


def test_ndss_parser_extracts_title_authors_and_url() -> None:
    """NDSS parser should extract papers from the accepted papers HTML."""

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


def test_usenix_parser_extracts_paper_and_authors() -> None:
    """USENIX parser should extract papers from technical session blocks."""

    html = """
    <div class="views-row">
      <h2><a href="/conference/usenixsecurity25/presentation/example-paper">USENIX Security Paper</a></h2>
      <div class="field field-name-field-paper-presenters">
        <div class="field-item">Maya Example, Nick Example</div>
      </div>
    </div>
    """
    crawler = USENIXSecurityCrawler()

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
