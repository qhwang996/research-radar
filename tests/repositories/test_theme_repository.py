"""Tests for the Theme repository."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.enums import ThemeStatus
from src.models.theme import Theme
from src.repositories.theme_repository import ThemeRepository


class ThemeRepositoryTestCase(unittest.TestCase):
    """Repository tests for theme lookup helpers."""

    def setUp(self) -> None:
        """Create an isolated database and theme repository."""

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()
        self.themes = ThemeRepository(self.session)

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_get_by_theme_id(self) -> None:
        """Business-key lookups should find a persisted theme."""

        theme = self.themes.save(self._build_theme(name="Web Fuzzing"))

        fetched = self.themes.get_by_theme_id(theme.theme_id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, theme.id)

    def test_list_by_status(self) -> None:
        """Status filtering should only return matching themes."""

        self.themes.save(self._build_theme(name="Candidate Theme", status=ThemeStatus.CANDIDATE))
        self.themes.save(self._build_theme(name="Core Theme", status=ThemeStatus.CORE))

        records = self.themes.list_by_status(ThemeStatus.CORE)

        self.assertEqual([record.name for record in records], ["Core Theme"])

    def test_list_active_or_core(self) -> None:
        """Candidate and core themes should be returned, archived excluded."""

        self.themes.save(self._build_theme(name="Candidate Theme", status=ThemeStatus.CANDIDATE))
        self.themes.save(self._build_theme(name="Core Theme", status=ThemeStatus.CORE))
        self.themes.save(self._build_theme(name="Archived Theme", status=ThemeStatus.ARCHIVED))

        records = self.themes.list_active_or_core()

        self.assertEqual({record.name for record in records}, {"Candidate Theme", "Core Theme"})

    def test_delete_candidates_by_version(self) -> None:
        """Candidate deletion should be scoped by version and preserve core rows."""

        candidate_v1 = self.themes.save(self._build_theme(name="Candidate V1", generation_version="v1"))
        self.themes.save(self._build_theme(name="Candidate V2", generation_version="v2"))
        self.themes.save(self._build_theme(name="Core V1", generation_version="v1", status=ThemeStatus.CORE))

        deleted = self.themes.delete_candidates_by_version("v1")

        remaining_names = {theme.name for theme in self.themes.list_all()}
        self.assertEqual(deleted, 1)
        self.assertNotIn(candidate_v1.name, remaining_names)
        self.assertIn("Candidate V2", remaining_names)
        self.assertIn("Core V1", remaining_names)

    def _build_theme(self, **kwargs) -> Theme:
        """Build one theme instance with sensible defaults."""

        return Theme(
            name=kwargs.pop("name", "Theme"),
            description=kwargs.pop("description", "Theme description"),
            keywords=kwargs.pop("keywords", ["web-security"]),
            artifact_ids=kwargs.pop("artifact_ids", [1, 2]),
            artifact_count=kwargs.pop("artifact_count", 2),
            paper_count_by_year=kwargs.pop("paper_count_by_year", {"2026": 2}),
            methodology_tags=kwargs.pop("methodology_tags", []),
            open_questions=kwargs.pop("open_questions", []),
            trend_direction=kwargs.pop("trend_direction", None),
            status=kwargs.pop("status", ThemeStatus.CANDIDATE),
            generation_version=kwargs.pop("generation_version", "v1"),
            week_id=kwargs.pop("week_id", "2026-W11"),
            **kwargs,
        )
