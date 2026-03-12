"""Tests for profile-aware relevance scoring."""

from __future__ import annotations

import unittest

from src.models.artifact import Artifact
from src.models.enums import SourceType
from src.models.profile import Profile
from src.scoring.relevance import RelevanceStrategy


class RelevanceStrategyTestCase(unittest.TestCase):
    """Unit tests for keyword-based relevance scoring."""

    def setUp(self) -> None:
        """Create a reusable strategy instance and baseline profile."""

        self.strategy = RelevanceStrategy()
        self.profile = Profile(
            profile_version="v1-test",
            current_research_area="Web应用安全与软件安全",
            interests=["Web漏洞检测"],
            preferred_topics=[],
            avoided_topics=[],
            is_active=True,
        )

    def test_no_profile_returns_neutral(self) -> None:
        """Missing profile should produce a neutral relevance score."""

        self.assertEqual(self.strategy.calculate_score(self._make_artifact(title="Generic Paper"), None), 0.5)

    def test_single_keyword_match(self) -> None:
        """One preferred-topic hit should score 0.4."""

        self.profile.preferred_topics = ["xss"]

        score = self.strategy.calculate_score(self._make_artifact(title="New XSS Detection Technique"), self.profile)

        self.assertEqual(score, 0.4)

    def test_multiple_keyword_match(self) -> None:
        """Three preferred-topic hits should score 0.8."""

        self.profile.preferred_topics = ["web-security", "fuzzing", "program-analysis"]
        artifact = self._make_artifact(
            title="Web Security Case Study",
            abstract="This paper combines fuzzing with program analysis for browser bugs.",
        )

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 0.8)

    def test_four_plus_keywords_caps_at_one(self) -> None:
        """Four or more preferred-topic hits should cap at 1.0."""

        self.profile.preferred_topics = ["web-security", "fuzzing", "program-analysis", "xss", "rce"]
        artifact = self._make_artifact(
            title="Web Security XSS Research",
            abstract="We use fuzzing and program analysis to study exploit chains and RCE.",
        )

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 1.0)

    def test_no_match_returns_floor(self) -> None:
        """No preferred-topic hits should keep the floor score."""

        self.profile.preferred_topics = ["xss", "sql-injection"]

        self.assertEqual(self.strategy.calculate_score(self._make_artifact(title="Kernel Scheduler Study"), self.profile), 0.1)

    def test_avoided_topic_penalty(self) -> None:
        """Avoided-topic hits should apply the penalty multiplier."""

        self.profile.preferred_topics = ["xss"]
        self.profile.avoided_topics = ["blockchain"]
        artifact = self._make_artifact(title="XSS Risks in Blockchain Wallet Extensions")

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 0.12)

    def test_tags_contribute_to_match(self) -> None:
        """Artifact tags should participate in preferred-topic matching."""

        self.profile.preferred_topics = ["supply-chain-security"]
        artifact = self._make_artifact(title="Artifact", tags=["supply_chain_security"])

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 0.4)

    def test_summary_l1_contributes_to_match(self) -> None:
        """summary_l1 should participate in preferred-topic matching."""

        self.profile.preferred_topics = ["java-security"]
        artifact = self._make_artifact(title="Artifact", summary_l1="A practical java security case study.")

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 0.4)

    def test_llm_relevance_score_read_from_breakdown(self) -> None:
        """Precomputed llm_relevance_score should be merged with keyword match."""

        self.profile.preferred_topics = ["xss"]
        artifact = self._make_artifact(
            title="New XSS Detection Technique",
            score_breakdown={"llm_relevance_score": 0.8},
        )

        breakdown = self.strategy.calculate_breakdown(artifact, self.profile)

        self.assertEqual(breakdown["keyword_match_score"], 0.4)
        self.assertEqual(breakdown["llm_relevance_score"], 0.8)
        self.assertEqual(breakdown["relevance_score"], 0.64)

    def test_llm_relevance_score_missing_falls_back_to_keyword_only(self) -> None:
        """Missing precomputed llm_relevance_score should fall back to keyword match only."""

        self.profile.preferred_topics = ["xss"]
        artifact = self._make_artifact(title="New XSS Detection Technique", score_breakdown={})

        self.assertEqual(self.strategy.calculate_score(artifact, self.profile), 0.4)

    def _make_artifact(
        self,
        *,
        title: str,
        abstract: str | None = None,
        summary_l1: str | None = None,
        tags: list[str] | None = None,
        score_breakdown: dict[str, float] | None = None,
    ) -> Artifact:
        """Create a lightweight artifact for relevance tests."""

        return Artifact(
            title=title,
            authors=["Alice Example"],
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="NDSS",
            source_url="https://example.com/artifact",
            abstract=abstract,
            summary_l1=summary_l1,
            tags=tags or [],
            score_breakdown=score_breakdown or {},
        )
