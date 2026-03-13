"""Tests for the weekly report generator."""

from __future__ import annotations

import re
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.enums import FeedbackTargetType, FeedbackType, SourceType
from src.models.feedback import FeedbackEvent
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.feedback_repository import FeedbackRepository
from src.reporting.weekly import WeeklyReportGenerator
from tests.reporting.helpers import make_artifact


class WeeklyReportGeneratorTestCase(unittest.TestCase):
    """Integration tests for the weekly report generator."""

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

    def test_weekly_empty_sections_render(self) -> None:
        """Empty weeks should still render the new weekly structure."""

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("## 本周论文推荐阅读（0 篇）", content)
        self.assertIn("暂无符合条件的未读论文推荐。", content)
        self.assertIn("## 本周博客回顾", content)
        self.assertIn("本周共收录 0 篇博客文章。", content)
        self.assertIn("本周无新增博客。", content)
        self.assertIn("- 本周新增论文: 0 篇", content)
        self.assertIn("- 本周新增博客: 0 篇", content)
        self.assertIn("- 数据库总量: 0 条", content)

    def test_weekly_recommends_up_to_ten_unread_high_relevance_papers(self) -> None:
        """Weekly paper recommendations should exclude read items and cap at ten."""

        unread_papers = [
            make_artifact(
                title=f"Unread Paper {index:02d}",
                source_type=SourceType.PAPERS,
                source_name="USENIX Security",
                final_score=0.99 - (index * 0.01),
                relevance_score=0.90,
                created_at=self.week_start - timedelta(days=index + 1),
            )
            for index in range(12)
        ]
        read_paper = make_artifact(
            title="Read Paper",
            source_type=SourceType.PAPERS,
            source_name="IEEE S&P",
            final_score=1.0,
            relevance_score=0.95,
            created_at=self.week_start - timedelta(days=30),
        )
        low_relevance_paper = make_artifact(
            title="Low Relevance Paper",
            source_type=SourceType.PAPERS,
            source_name="NDSS",
            final_score=0.98,
            relevance_score=0.55,
            created_at=self.week_start - timedelta(days=2),
        )

        self._save_artifacts(*unread_papers, read_paper, low_relevance_paper)
        self._mark_as_read(read_paper)

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")
        paper_section = content.split("## 本周博客回顾", maxsplit=1)[0]

        self.assertIn("## 本周论文推荐阅读（10 篇）", paper_section)
        self.assertEqual(len(re.findall(r"^### \d+\. ", paper_section, flags=re.MULTILINE)), 10)
        self.assertIn("Unread Paper 00", paper_section)
        self.assertIn("Unread Paper 09", paper_section)
        self.assertNotIn("Unread Paper 10", paper_section)
        self.assertNotIn("Unread Paper 11", paper_section)
        self.assertNotIn("Read Paper", paper_section)
        self.assertNotIn("Low Relevance Paper", paper_section)

    def test_weekly_blog_review_table_shows_read_status(self) -> None:
        """Weekly blog recap should render a table and mark read state per artifact."""

        read_blog = make_artifact(
            title="Read Blog",
            source_type=SourceType.BLOGS,
            source_name="Project Zero",
            final_score=0.88,
            relevance_score=0.91,
            created_at=self.week_start + timedelta(hours=1),
        )
        unread_blog = make_artifact(
            title="Unread Blog",
            source_type=SourceType.BLOGS,
            source_name="PortSwigger Research",
            final_score=0.82,
            relevance_score=0.72,
            created_at=self.week_start + timedelta(hours=2),
        )

        self._save_artifacts(read_blog, unread_blog)
        self._mark_as_read(read_blog)

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("| # | 标题 | 来源 | 相关度 | 状态 |", content)
        self.assertIn("| 1 | Read Blog | Project Zero | 0.91 | 已读 |", content)
        self.assertIn("| 2 | Unread Blog | PortSwigger Research | 0.72 | 未读 |", content)

    def test_weekly_recommends_historical_papers_not_just_current_week(self) -> None:
        """Weekly paper recommendations should pull from the broader unread corpus."""

        self._save_artifacts(
            make_artifact(
                title="Historical Paper",
                source_type=SourceType.PAPERS,
                source_name="IEEE S&P",
                final_score=0.97,
                relevance_score=0.88,
                created_at=self.week_start - timedelta(days=21),
            )
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")
        paper_section = content.split("## 本周博客回顾", maxsplit=1)[0]

        self.assertIn("Historical Paper", paper_section)
        self.assertIn("- 本周新增论文: 0 篇", content)

    def test_weekly_paper_summary_uses_summary_l1_when_abstract_missing(self) -> None:
        """Paper recommendations should fall back to summary_l1 when abstract is absent."""

        self._save_artifacts(
            make_artifact(
                title="Summary Fallback Paper",
                source_type=SourceType.PAPERS,
                source_name="NDSS",
                abstract=None,
                summary_l1="Paper summary from L1.",
                final_score=0.94,
                relevance_score=0.84,
                created_at=self.week_start - timedelta(days=7),
            )
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("Paper summary from L1.", content)
        self.assertNotIn("暂无摘要。", content)

    def test_weekly_blog_review_excludes_blogs_outside_week(self) -> None:
        """Weekly blog recap should only list blogs created within the target week."""

        self._save_artifacts(
            make_artifact(
                title="In Week Blog",
                source_type=SourceType.BLOGS,
                source_name="Project Zero",
                final_score=0.84,
                relevance_score=0.77,
                created_at=self.week_start + timedelta(days=1),
            ),
            make_artifact(
                title="Old Blog",
                source_type=SourceType.BLOGS,
                source_name="PortSwigger Research",
                final_score=0.83,
                relevance_score=0.76,
                created_at=self.week_start - timedelta(days=1),
            ),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")
        blog_section = content.split("## Relevance Distribution", maxsplit=1)[0]

        self.assertIn("In Week Blog", blog_section)
        self.assertNotIn("Old Blog", blog_section)

    def test_weekly_distributions_and_stats_use_week_window(self) -> None:
        """Distribution buckets and stats should reflect artifacts created in the target week."""

        self._save_artifacts(
            make_artifact(
                title="Week Paper High",
                source_type=SourceType.PAPERS,
                source_name="IEEE S&P",
                final_score=0.95,
                relevance_score=0.82,
                created_at=self.week_start,
            ),
            make_artifact(
                title="Week Paper Medium",
                source_type=SourceType.PAPERS,
                source_name="USENIX Security",
                final_score=0.75,
                relevance_score=0.45,
                created_at=self.week_start + timedelta(hours=1),
            ),
            make_artifact(
                title="Week Blog Low",
                source_type=SourceType.BLOGS,
                source_name="Cloudflare Security Blog",
                final_score=0.55,
                relevance_score=0.20,
                created_at=self.week_start + timedelta(hours=2),
            ),
            make_artifact(
                title="Outside Week Paper",
                source_type=SourceType.PAPERS,
                source_name="NDSS",
                final_score=0.91,
                relevance_score=0.88,
                created_at=self.week_start - timedelta(days=1),
            ),
        )

        content = self.generator.generate(self.target_date).read_text(encoding="utf-8")

        self.assertIn("## Relevance Distribution", content)
        self.assertIn("- 高相关 (>= 0.6): 1 items", content)
        self.assertIn("- 中等 (0.3 - 0.6): 1 items", content)
        self.assertIn("- 低相关 (< 0.3): 1 items", content)
        self.assertIn("## Score Distribution", content)
        self.assertIn("- >= 0.9: 1 items", content)
        self.assertIn("- 0.8-0.9: 0 items", content)
        self.assertIn("- 0.7-0.8: 1 items", content)
        self.assertIn("- 0.6-0.7: 0 items", content)
        self.assertIn("- < 0.6: 1 items", content)
        self.assertIn("- 本周新增论文: 2 篇", content)
        self.assertIn("- 本周新增博客: 1 篇", content)
        self.assertIn("- 数据库总量: 4 条", content)

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

    def _mark_as_read(self, artifact) -> None:
        """Persist a read feedback event for an artifact."""

        session: Session = self.session_factory()
        try:
            FeedbackRepository(session).save(
                FeedbackEvent(
                    target_type=FeedbackTargetType.ARTIFACT,
                    target_id=str(artifact.id),
                    feedback_type=FeedbackType.READ,
                    content={"type": "read"},
                )
            )
        finally:
            session.close()
