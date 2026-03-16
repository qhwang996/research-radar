"""Tests for the gap detection pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType, ThemeStatus
from src.models.theme import Theme
from src.pipelines.gap_detection import GapDetectionPipeline
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.theme_repository import ThemeRepository


class GapDetectionPipelineTestCase(unittest.TestCase):
    """Tests for statistical gap detection between academic and industry tracks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_detects_gap_when_demand_exceeds_coverage(self) -> None:
        """A demand topic with no academic coverage should produce a high gap score."""

        # Create a theme covering "fuzzing" but not "ssrf detection"
        self._save_theme(
            name="Web Fuzzing",
            keywords=["fuzzing", "web application testing"],
            artifact_ids=[1],
        )

        # Create blog with demand signal mentioning "ssrf detection"
        self._save_blog_with_signal(
            title="Blog A",
            signal={
                "signal_type": "demand",
                "problem_described": "SSRF 检测难以自动化",
                "affected_systems": ["Web 应用"],
                "current_solutions": "手动审计",
                "solution_gaps": ["缺少自动化 SSRF 链检测"],
                "urgency_indicators": ["云原生普及"],
                "related_academic_topics": ["ssrf detection", "vulnerability detection"],
            },
        )
        self._save_blog_with_signal(
            title="Blog B",
            signal={
                "signal_type": "demand",
                "problem_described": "SSRF 在微服务中更普遍",
                "affected_systems": ["微服务"],
                "current_solutions": "WAF",
                "solution_gaps": ["WAF 无法覆盖内部服务"],
                "urgency_indicators": ["微服务增长"],
                "related_academic_topics": ["ssrf detection"],
            },
        )

        pipeline = GapDetectionPipeline(session_factory=self.session_factory, top_n=5)
        gaps = pipeline.process()

        self.assertGreater(len(gaps), 0)
        # "ssrf detection" should be the top gap (2 sources, no academic coverage)
        top_gap = gaps[0]
        self.assertEqual(top_gap.topic, "ssrf detection")
        self.assertEqual(top_gap.demand_frequency, 2)
        self.assertGreater(top_gap.gap_score, 0)

    def test_no_gaps_when_no_demand_signals(self) -> None:
        """Pipeline should return empty when there are no blog demand signals."""

        self._save_theme(name="Web Fuzzing", keywords=["fuzzing"])

        pipeline = GapDetectionPipeline(session_factory=self.session_factory)
        gaps = pipeline.process()

        self.assertEqual(gaps, [])

    def test_covered_topic_has_low_gap_score(self) -> None:
        """A demand topic well-covered by academic themes should have low/zero gap score."""

        self._save_theme(
            name="Web Fuzzing",
            keywords=["fuzzing", "web fuzzing", "web application fuzzing"],
            artifact_ids=[1],
        )

        self._save_blog_with_signal(
            title="Blog C",
            signal={
                "signal_type": "demand",
                "problem_described": "Fuzzing 效率问题",
                "affected_systems": ["Web 应用"],
                "current_solutions": "现有 fuzzer",
                "solution_gaps": ["覆盖率不足"],
                "urgency_indicators": ["复杂应用增加"],
                "related_academic_topics": ["fuzzing"],
            },
        )

        pipeline = GapDetectionPipeline(session_factory=self.session_factory, top_n=5)
        gaps = pipeline.process()

        # "fuzzing" should have high coverage, so gap_score should be low or 0
        fuzzing_gaps = [g for g in gaps if g.topic == "fuzzing"]
        if fuzzing_gaps:
            self.assertLessEqual(fuzzing_gaps[0].gap_score, 0.5)

    def _save_theme(self, **kwargs) -> Theme:
        session: Session = self.session_factory()
        try:
            repo = ThemeRepository(session)
            return repo.save(
                Theme(
                    name=kwargs.pop("name", "Test Theme"),
                    keywords=kwargs.pop("keywords", []),
                    artifact_ids=kwargs.pop("artifact_ids", []),
                    artifact_count=len(kwargs.get("artifact_ids", [])),
                    status=kwargs.pop("status", ThemeStatus.CANDIDATE),
                    generation_version="v1",
                    week_id="2026-W11",
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_blog_with_signal(self, title: str, signal: dict) -> Artifact:
        session: Session = self.session_factory()
        try:
            repo = ArtifactRepository(session)
            return repo.save(
                Artifact(
                    title=title,
                    authors=["Blogger"],
                    year=2026,
                    source_type=SourceType.BLOGS,
                    source_tier="t3-research-blog",
                    source_name="PortSwigger Research",
                    source_url=f"https://example.com/{title.lower().replace(' ', '-')}",
                    abstract="Blog post.",
                    summary_l2=json.dumps(signal, ensure_ascii=False),
                    status=ArtifactStatus.ACTIVE,
                )
            )
        finally:
            session.close()
