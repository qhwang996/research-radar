"""Tests for scoring strategies and batch scoring engine."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.models.profile import Profile
from src.repositories.artifact_repository import ArtifactRepository
from src.scoring.authority import AuthorityStrategy
from src.scoring.composite import CompositeStrategy
from src.scoring.engine import ScoringEngine
from src.scoring.recency import RecencyStrategy


class ScoringStrategyTestCase(unittest.TestCase):
    """Unit tests for standalone scoring strategies."""

    def setUp(self) -> None:
        """Provide a fixed clock for deterministic recency scoring."""

        self.now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

    def test_recency_strategy_prefers_recent_top_tier_papers(self) -> None:
        """Recent top-tier papers should outscore older top-tier papers."""

        strategy = RecencyStrategy(now=self.now)
        recent = Artifact(
            title="Recent Paper",
            authors=["Alice"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="USENIX Security",
            source_url="https://example.com/recent-paper",
            published_at=self.now - timedelta(days=180),
        )
        older = Artifact(
            title="Older Paper",
            authors=["Alice"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="USENIX Security",
            source_url="https://example.com/older-paper",
            published_at=self.now - timedelta(days=1400),
        )

        self.assertGreater(strategy.calculate_score(recent), strategy.calculate_score(older))
        self.assertEqual(strategy.calculate_score(recent), 1.0)
        self.assertEqual(strategy.calculate_score(older), 0.8)

    def test_recency_strategy_uses_blog_curve(self) -> None:
        """High-quality blogs should use the blog-specific recency curve."""

        strategy = RecencyStrategy(now=self.now)
        artifact = Artifact(
            title="Fresh Blog",
            authors=["Researcher"],
            source_type=SourceType.BLOGS,
            source_tier="high-quality-blog",
            source_name="PortSwigger Research",
            source_url="https://example.com/blog",
            published_at=self.now - timedelta(days=75),
        )

        self.assertEqual(strategy.calculate_score(artifact), 0.95)

    def test_authority_strategy_uses_source_tier_and_name(self) -> None:
        """Authority scores should match the configured source hierarchy."""

        strategy = AuthorityStrategy()
        conference = Artifact(
            title="Conference",
            authors=["Alice"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="ACM CCS",
            source_url="https://example.com/ccs",
        )
        blog = Artifact(
            title="Blog",
            authors=["Researcher"],
            source_type=SourceType.BLOGS,
            source_tier="high-quality-blog",
            source_name="PortSwigger Research",
            source_url="https://example.com/blog",
        )
        preprint = Artifact(
            title="Preprint",
            authors=["Researcher"],
            source_type=SourceType.PAPERS,
            source_tier="paper",
            source_name="arXiv",
            source_url="https://example.com/arxiv",
        )

        self.assertEqual(strategy.calculate_score(conference), 1.0)
        self.assertEqual(strategy.calculate_score(blog), 0.7)
        self.assertEqual(strategy.calculate_score(preprint), 0.5)

    def test_composite_strategy_averages_recency_and_authority(self) -> None:
        """Phase 1 composite score should average recency and authority."""

        strategy = CompositeStrategy(
            recency_strategy=RecencyStrategy(now=self.now),
            authority_strategy=AuthorityStrategy(),
        )
        artifact = Artifact(
            title="Conference",
            authors=["Alice"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="NDSS",
            source_url="https://example.com/ndss",
            published_at=self.now - timedelta(days=500),
        )

        breakdown = strategy.calculate_breakdown(artifact)

        self.assertEqual(breakdown["recency_score"], 0.95)
        self.assertEqual(breakdown["authority_score"], 1.0)
        self.assertEqual(breakdown["final_score"], 0.975)


class ScoringEngineIntegrationTestCase(unittest.TestCase):
    """Integration tests for scoring persisted artifacts."""

    def setUp(self) -> None:
        """Create an isolated database and scoring engine."""

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.fixed_now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        self.scoring_engine = ScoringEngine(
            session_factory=self.session_factory,
            composite_strategy=CompositeStrategy(
                recency_strategy=RecencyStrategy(now=self.fixed_now),
                authority_strategy=AuthorityStrategy(),
            ),
        )

    def tearDown(self) -> None:
        """Dispose resources created for the test."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_score_all_persists_scores_and_ranks_recent_top_tier_first(self) -> None:
        """Batch scoring should persist breakdowns and rank recent top-tier work highest."""

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            recent_paper = repository.save(
                Artifact(
                    title="Recent Top Tier Paper",
                    authors=["Alice"],
                    source_type=SourceType.PAPERS,
                    source_tier="top-tier",
                    source_name="USENIX Security",
                    source_url="https://example.com/recent-paper",
                    published_at=self.fixed_now - timedelta(days=120),
                    status=ArtifactStatus.ACTIVE,
                )
            )
            recent_blog = repository.save(
                Artifact(
                    title="Recent Blog",
                    authors=["Researcher"],
                    source_type=SourceType.BLOGS,
                    source_tier="high-quality-blog",
                    source_name="PortSwigger Research",
                    source_url="https://example.com/recent-blog",
                    published_at=self.fixed_now - timedelta(days=20),
                    status=ArtifactStatus.ACTIVE,
                )
            )
            old_paper = repository.save(
                Artifact(
                    title="Old Paper",
                    authors=["Alice"],
                    source_type=SourceType.PAPERS,
                    source_tier="top-tier",
                    source_name="IEEE S&P",
                    source_url="https://example.com/old-paper",
                    published_at=self.fixed_now - timedelta(days=2200),
                    status=ArtifactStatus.ACTIVE,
                )
            )
            session.add(
                Profile(
                    profile_version="v1",
                    interests=["web security"],
                    preferences={},
                    is_active=True,
                )
            )
            session.commit()
        finally:
            session.close()

        scored = self.scoring_engine.score_all()

        self.assertEqual(len(scored), 3)
        self.assertEqual(scored[0].title, recent_paper.title)
        self.assertGreater(scored[0].final_score, scored[1].final_score)
        self.assertGreater(scored[1].final_score, scored[2].final_score)
        self.assertGreater(scored[0].final_score, recent_blog.final_score or 0.0)

        session = self.session_factory()
        try:
            artifacts = ArtifactRepository(session).list_by_status(ArtifactStatus.ACTIVE)
            scores_by_title = {artifact.title: artifact for artifact in artifacts}
            self.assertEqual(scores_by_title["Recent Top Tier Paper"].recency_score, 1.0)
            self.assertEqual(scores_by_title["Recent Top Tier Paper"].authority_score, 1.0)
            self.assertEqual(scores_by_title["Recent Top Tier Paper"].final_score, 1.0)
            self.assertEqual(
                scores_by_title["Recent Blog"].score_breakdown["authority_score"],
                0.7,
            )
            self.assertIn("weights", scores_by_title["Old Paper"].score_breakdown)
        finally:
            session.close()
