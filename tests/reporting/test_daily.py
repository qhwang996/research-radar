"""Tests for the daily report generator."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.repositories.artifact_repository import ArtifactRepository
from src.reporting.daily import DailyReportGenerator
from tests.reporting.helpers import make_artifact


class DailyReportGeneratorTestCase(unittest.TestCase):
    """Integration tests for daily report generation."""

    def setUp(self) -> None:
        """Create an isolated database and output directory."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.output_dir = self.workspace / "reports"
        self.generator = DailyReportGenerator(
            session_factory=self.session_factory,
            output_dir=self.output_dir,
        )
        self.generator._current_time = lambda: datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc)  # type: ignore[method-assign]
        self.target_date = date(2026, 3, 10)

    def tearDown(self) -> None:
        """Dispose resources created for the test."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_daily_empty(self) -> None:
        """Empty days should still produce a report file."""

        report_path = self.generator.generate(self.target_date)
        content = report_path.read_text(encoding="utf-8")

        self.assertTrue(report_path.exists())
        self.assertIn("No artifacts found", content)

    def test_daily_score_filter(self) -> None:
        """Artifacts below the reporting threshold should be excluded."""

        self._save_artifacts(
            make_artifact(title="High Value", final_score=0.91),
            make_artifact(title="Medium Value", final_score=0.65),
            make_artifact(title="Low Value", final_score=0.59),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("High Value", content)
        self.assertIn("Medium Value", content)
        self.assertNotIn("Low Value", content)

    def test_daily_high_value_has_abstract(self) -> None:
        """High-value entries should show truncated abstracts."""

        self._save_artifacts(
            make_artifact(
                title="Important Paper",
                final_score=0.88,
                abstract="A" * 260,
            )
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("**Abstract**: ", content)
        self.assertIn(("A" * 197) + "...", content)

    def test_daily_medium_value_no_abstract(self) -> None:
        """Medium-value entries should omit abstracts."""

        self._save_artifacts(
            make_artifact(
                title="Worth Reading",
                final_score=0.72,
                abstract="This abstract should not be displayed.",
            )
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("Worth Reading", content)
        self.assertNotIn("This abstract should not be displayed.", content)

    def test_daily_sorted_by_score(self) -> None:
        """Entries should be sorted by score descending within report sections."""

        self._save_artifacts(
            make_artifact(title="Lower Ranked", final_score=0.81),
            make_artifact(title="Higher Ranked", final_score=0.95),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertLess(content.index("Higher Ranked"), content.index("Lower Ranked"))

    def test_daily_file_written(self) -> None:
        """Daily reports should be written to the expected path."""

        report_path = self.generator.generate(self.target_date)

        self.assertEqual(report_path, (self.output_dir / "daily" / "2026-03-10.md").resolve())
        self.assertTrue(report_path.exists())

    def test_daily_idempotent(self) -> None:
        """Running twice should overwrite the same file with the same content."""

        self._save_artifacts(make_artifact(title="Stable Artifact", final_score=0.8))

        first_path = self.generator.generate(self.target_date)
        first_content = first_path.read_text(encoding="utf-8")
        second_path = self.generator.generate(self.target_date)
        second_content = second_path.read_text(encoding="utf-8")

        self.assertEqual(first_path, second_path)
        self.assertEqual(first_content, second_content)

    def _save_artifacts(self, *artifacts) -> None:
        """Persist artifacts for report-generation tests."""

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            for artifact in artifacts:
                repository.save(artifact)
        finally:
            session.close()
