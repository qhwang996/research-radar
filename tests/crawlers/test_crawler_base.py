"""Tests for shared crawler behavior."""

from __future__ import annotations

import json
from pathlib import Path

from src.crawlers.base import PaperCrawler


class DummyPaperCrawler(PaperCrawler):
    """Minimal paper crawler for testing shared behavior."""

    source_name = "Dummy Papers"
    source_slug = "dummy_papers"

    def fetch_papers(self, years: list[int]) -> list[dict[str, object]]:
        """Return one synthetic paper."""

        return [{"title": "Dummy", "year": years[0]}]


def test_save_raw_includes_required_metadata(tmp_path: Path) -> None:
    """save_raw should include source metadata and total counts."""

    crawler = DummyPaperCrawler()
    output_path = crawler.save_raw(
        [{"title": "Dummy", "year": 2025}],
        tmp_path,
        metadata={"years": [2025]},
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["source"] == "Dummy Papers"
    assert payload["source_type"] == "papers"
    assert payload["total_items"] == 1
    assert payload["total_papers"] == 1
    assert payload["years"] == [2025]
    assert payload["items"][0]["title"] == "Dummy"
