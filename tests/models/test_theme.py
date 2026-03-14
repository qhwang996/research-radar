"""Tests for the Theme ORM model."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.enums import ThemeStatus
from src.models.theme import Theme


class ThemeModelTestCase(unittest.TestCase):
    """Tests for Theme model persistence behavior."""

    def setUp(self) -> None:
        """Create an isolated database and session."""

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_theme_creation(self) -> None:
        """Theme rows should persist the configured clustering metadata."""

        theme = Theme(
            name="Web Application Fuzzing",
            description="A cluster about fuzzing web application attack surfaces.",
            keywords=["web-fuzzing", "server-side", "inputs"],
            artifact_ids=[1, 2, 3],
            artifact_count=3,
            paper_count_by_year={"2024": 1, "2025": 2},
            methodology_tags=["dynamic-analysis"],
            open_questions=["How to reduce false positives?"],
            trend_direction="growing",
            status=ThemeStatus.CORE,
            generation_version="v1",
            week_id="2026-W11",
        )

        self.session.add(theme)
        self.session.commit()
        self.session.refresh(theme)

        self.assertIsNotNone(theme.id)
        self.assertTrue(theme.theme_id)
        self.assertEqual(theme.status, ThemeStatus.CORE)
        self.assertEqual(theme.artifact_count, 3)
        self.assertEqual(theme.paper_count_by_year["2025"], 2)

    def test_theme_status_default(self) -> None:
        """Theme status should default to candidate."""

        theme = Theme(
            name="Browser Security",
            description=None,
            keywords=["browser"],
            artifact_ids=[1],
            artifact_count=1,
            paper_count_by_year={"2026": 1},
            generation_version="v1",
            week_id="2026-W11",
        )

        self.session.add(theme)
        self.session.commit()
        self.session.refresh(theme)

        self.assertEqual(theme.status, ThemeStatus.CANDIDATE)

    def test_theme_json_fields(self) -> None:
        """Mutable JSON fields should round-trip as native Python structures."""

        theme = Theme(
            name="JavaScript Security",
            description="Cluster for client-side security work.",
            keywords=["dom-xss", "javascript"],
            artifact_ids=[10, 11],
            artifact_count=2,
            paper_count_by_year={"2023": 1, "2026": 1},
            methodology_tags=["taint-analysis", "fuzzing"],
            open_questions=["How to model framework-specific sanitizers?"],
            generation_version="v1",
            week_id="2026-W11",
        )

        self.session.add(theme)
        self.session.commit()
        self.session.refresh(theme)

        self.assertEqual(theme.keywords, ["dom-xss", "javascript"])
        self.assertEqual(theme.artifact_ids, [10, 11])
        self.assertEqual(theme.paper_count_by_year, {"2023": 1, "2026": 1})
        self.assertEqual(theme.methodology_tags, ["taint-analysis", "fuzzing"])
