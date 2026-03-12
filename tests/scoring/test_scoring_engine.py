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
from src.scoring.relevance import RelevanceStrategy
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

    def test_recency_strategy_prefers_year_over_fetched_at_fallback(self) -> None:
        """Year metadata should outrank fetch time when publish time is missing."""

        strategy = RecencyStrategy(now=self.now)
        artifact = Artifact(
            title="Archived Paper",
            authors=["Researcher"],
            year=2022,
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="USENIX Security",
            source_url="https://example.com/archived-paper",
            published_at=None,
            fetched_at=self.now - timedelta(days=1),
        )

        self.assertEqual(strategy.calculate_score(artifact), 0.8)
        self.assertLess(strategy.calculate_score(artifact), 1.0)

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

    def test_composite_strategy_combines_all_three_score_components(self) -> None:
        """Composite scoring should apply recency, authority, and relevance weights."""

        strategy = CompositeStrategy(
            recency_strategy=RecencyStrategy(now=self.now),
            authority_strategy=AuthorityStrategy(),
            relevance_strategy=RelevanceStrategy(),
        )
        artifact = Artifact(
            title="Conference XSS Study",
            authors=["Alice"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="NDSS",
            source_url="https://example.com/ndss",
            published_at=self.now - timedelta(days=500),
            abstract="A practical web security evaluation for browser defenses.",
        )
        profile = Profile(
            profile_version="v1",
            interests=["web security"],
            preferred_topics=["xss", "web-security"],
            avoided_topics=[],
            is_active=True,
        )

        breakdown = strategy.calculate_breakdown(artifact, profile)

        self.assertEqual(breakdown["recency_score"], 0.95)
        self.assertEqual(breakdown["authority_score"], 1.0)
        self.assertEqual(breakdown["relevance_score"], 0.6)
        self.assertEqual(breakdown["final_score"], 0.86)
        self.assertEqual(breakdown["formula"], "final_score = recency * 0.4 + authority * 0.3 + relevance * 0.3")
        self.assertEqual(breakdown["version"], "phase2-v1")


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
                    title="Recent Top Tier XSS Paper",
                    authors=["Alice"],
                    source_type=SourceType.PAPERS,
                    source_tier="top-tier",
                    source_name="USENIX Security",
                    source_url="https://example.com/recent-paper",
                    published_at=self.fixed_now - timedelta(days=120),
                    abstract="A web security paper on XSS gadget discovery.",
                    status=ArtifactStatus.ACTIVE,
                )
            )
            recent_blog = repository.save(
                Artifact(
                    title="Recent Fuzzing Blog",
                    authors=["Researcher"],
                    source_type=SourceType.BLOGS,
                    source_tier="high-quality-blog",
                    source_name="PortSwigger Research",
                    source_url="https://example.com/recent-blog",
                    published_at=self.fixed_now - timedelta(days=20),
                    summary_l1="A fuzzing workflow for web targets.",
                    status=ArtifactStatus.ACTIVE,
                )
            )
            old_paper = repository.save(
                Artifact(
                    title="Old Blockchain Paper",
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
                    preferred_topics=["xss", "web-security", "fuzzing"],
                    avoided_topics=["blockchain"],
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
            self.assertEqual(scores_by_title["Recent Top Tier XSS Paper"].recency_score, 1.0)
            self.assertEqual(scores_by_title["Recent Top Tier XSS Paper"].authority_score, 1.0)
            self.assertEqual(scores_by_title["Recent Top Tier XSS Paper"].relevance_score, 0.6)
            self.assertEqual(scores_by_title["Recent Top Tier XSS Paper"].final_score, 0.88)
            self.assertEqual(
                scores_by_title["Recent Fuzzing Blog"].score_breakdown["authority_score"],
                0.7,
            )
            self.assertEqual(scores_by_title["Old Blockchain Paper"].relevance_score, 0.03)
            self.assertIn("weights", scores_by_title["Old Blockchain Paper"].score_breakdown)
        finally:
            session.close()
