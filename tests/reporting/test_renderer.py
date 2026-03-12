"""Tests for markdown rendering helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.reporting.renderer import format_date, format_score, truncate


class RendererTestCase(unittest.TestCase):
    """Unit tests for pure renderer helpers."""

    def test_truncate_short_text(self) -> None:
        """Short text should be returned unchanged."""

        self.assertEqual(truncate("short text", 20), "short text")

    def test_truncate_long_text(self) -> None:
        """Long text should be truncated with a suffix."""

        self.assertEqual(truncate("abcdefghij", 8), "abcde...")

    def test_format_score(self) -> None:
        """Scores should include breakdown components when available."""

        self.assertEqual(
            format_score(0.95, 0.9, 1.0, 0.64),
            "0.95 (recency: 0.90, authority: 1.00, relevance: 0.64)",
        )

    def test_format_date_with_datetime(self) -> None:
        """Datetime display should use an ISO-style calendar date."""

        self.assertEqual(
            format_date(datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc)),
            "2026-03-10",
        )

    def test_format_date_with_year_only(self) -> None:
        """Year should be used when a full date is unavailable."""

        self.assertEqual(format_date(None, year=2026), "2026")
