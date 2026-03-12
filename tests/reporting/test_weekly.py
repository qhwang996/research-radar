"""Tests for the weekly report generator."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.enums import SourceType
from src.repositories.artifact_repository import ArtifactRepository
from src.reporting.weekly import WeeklyReportGenerator
from tests.reporting.helpers import make_artifact


class WeeklyReportGeneratorTestCase(unittest.TestCase):
    """Integration tests for weekly report generation."""

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
        self.generator = WeeklyReportGenerator(
            session_factory=self.session_factory,
            output_dir=self.output_dir,
            now_fn=lambda: datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc),
        )
        self.target_date = date(2026, 3, 10)
        self.week_start = datetime(2026, 3, 9, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        """Dispose resources created for the test."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_weekly_empty(self) -> None:
        """Empty weeks should still produce a report file."""

        report_path = self.generator.generate(self.target_date)
        content = report_path.read_text(encoding="utf-8")

        self.assertTrue(report_path.exists())
        self.assertIn("No artifacts found", content)

    def test_weekly_top_30(self) -> None:
        """The top section should include up to the thirty highest-scoring artifacts."""

        artifacts = [
            make_artifact(
                title=f"Artifact {index:02d}",
                final_score=1.0 - (index * 0.01),
                created_at=self.week_start + timedelta(hours=index),
            )
            for index in range(32)
        ]
        self._save_artifacts(*artifacts)

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")
        top_section = content.split("## Score Distribution", maxsplit=1)[0]

        self.assertIn("## Top 30 Artifacts", top_section)
        self.assertIn("Artifact 00", top_section)
        self.assertIn("Artifact 29", top_section)
        self.assertNotIn("Artifact 30", top_section)
        self.assertNotIn("Artifact 31", top_section)

    def test_weekly_score_distribution(self) -> None:
        """Score buckets should match the included artifacts."""

        self._save_artifacts(
            make_artifact(title="Bucket A", final_score=0.95, created_at=self.week_start),
            make_artifact(title="Bucket B", final_score=0.85, created_at=self.week_start + timedelta(hours=1)),
            make_artifact(title="Bucket C", final_score=0.75, created_at=self.week_start + timedelta(hours=2)),
            make_artifact(title="Bucket D", final_score=0.65, created_at=self.week_start + timedelta(hours=3)),
            make_artifact(title="Bucket E", final_score=0.55, created_at=self.week_start + timedelta(hours=4)),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("- >= 0.9: 1 items", content)
        self.assertIn("- 0.8-0.9: 1 items", content)
        self.assertIn("- 0.7-0.8: 1 items", content)
        self.assertIn("- 0.6-0.7: 1 items", content)
        self.assertIn("- < 0.6: 1 items", content)

    def test_weekly_relevance_distribution(self) -> None:
        """Weekly reports should include the relevance-score distribution."""

        self._save_artifacts(
            make_artifact(title="High Relevance", relevance_score=0.8, created_at=self.week_start),
            make_artifact(title="Medium Relevance", relevance_score=0.4, created_at=self.week_start + timedelta(hours=1)),
            make_artifact(title="Low Relevance", relevance_score=0.2, created_at=self.week_start + timedelta(hours=2)),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("## Relevance Distribution", content)
        self.assertIn("- 高相关 (>= 0.6): 1 items", content)
        self.assertIn("- 中等 (0.3 - 0.6): 1 items", content)
        self.assertIn("- 低相关 (< 0.3): 1 items", content)

    def test_weekly_omits_all_artifacts_by_source_section(self) -> None:
        """Weekly reports should no longer render the full grouped artifact list."""

        self._save_artifacts(
            make_artifact(title="Paper A", source_type=SourceType.PAPERS, created_at=self.week_start),
            make_artifact(title="Blog A", source_type=SourceType.BLOGS, created_at=self.week_start + timedelta(hours=1)),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertNotIn("## All Artifacts by Source", content)

    def test_weekly_content_breakdown(self) -> None:
        """Weekly reports should summarize source-type counts."""

        self._save_artifacts(
            make_artifact(title="Paper A", source_type=SourceType.PAPERS, source_tier="top-tier", created_at=self.week_start),
            make_artifact(title="Paper B", source_type=SourceType.PAPERS, source_tier="paper", created_at=self.week_start + timedelta(hours=1)),
            make_artifact(title="Blog A", source_type=SourceType.BLOGS, source_name="PortSwigger Research", source_tier="high-quality-blog", created_at=self.week_start + timedelta(hours=2)),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("- Papers: 2 (top-tier: 1)", content)
        self.assertIn("- Blogs: 1", content)

    def test_weekly_date_range(self) -> None:
        """Only artifacts created within the ISO week should be included."""

        self._save_artifacts(
            make_artifact(title="In Week", created_at=self.week_start + timedelta(days=1)),
            make_artifact(title="Before Week", created_at=self.week_start - timedelta(days=1)),
            make_artifact(title="After Week", created_at=self.week_start + timedelta(days=7)),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("In Week", content)
        self.assertNotIn("Before Week", content)
        self.assertNotIn("After Week", content)

    def test_weekly_file_naming(self) -> None:
        """Weekly reports should use ISO week naming."""

        report_path = self.generator.generate(self.target_date)
        iso_year, iso_week, _ = self.target_date.isocalendar()

        self.assertEqual(
            report_path,
            (self.output_dir / "weekly" / f"{iso_year}-W{iso_week:02d}.md").resolve(),
        )
        self.assertTrue(report_path.exists())

    def _save_artifacts(self, *artifacts) -> None:
        """Persist artifacts for report-generation tests."""

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            for artifact in artifacts:
                repository.save(artifact)
        finally:
            session.close()
