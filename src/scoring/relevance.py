"""Profile-aware relevance scoring strategy."""

from __future__ import annotations

import re

from src.models.artifact import Artifact
from src.models.profile import Profile
from src.scoring.base import BaseScoringStrategy

TOPIC_AVOIDANCE_PENALTY = 0.3
NEUTRAL_RELEVANCE_SCORE = 0.5
NO_MATCH_FLOOR_SCORE = 0.1
KEYWORD_LLM_WEIGHT = 0.4
LLM_RELEVANCE_WEIGHT = 0.6


class RelevanceStrategy(BaseScoringStrategy):
    """Score artifacts by matching profile topics against artifact content."""

    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return the final relevance score for one artifact/profile pair."""

        return float(self.calculate_breakdown(artifact, profile)["relevance_score"])

    def calculate_breakdown(self, artifact: Artifact, profile: Profile | None = None) -> dict[str, float | None]:
        """Return keyword-match details and the merged relevance score."""

        if profile is None:
            return {
                "keyword_match_score": NEUTRAL_RELEVANCE_SCORE,
                "llm_relevance_score": None,
                "relevance_score": NEUTRAL_RELEVANCE_SCORE,
            }

        search_corpus = self._build_search_corpus(artifact)
        preferred_match_count = self._count_topic_matches(profile.preferred_topics, search_corpus)
        avoided_match_count = self._count_topic_matches(profile.avoided_topics, search_corpus)
        keyword_match_score = self._score_from_match_count(preferred_match_count)
        llm_relevance_score = self._calculate_llm_relevance_score(artifact, profile)
        relevance_score = self._merge_relevance_scores(keyword_match_score, llm_relevance_score)
        if avoided_match_count:
            relevance_score *= TOPIC_AVOIDANCE_PENALTY

        return {
            "keyword_match_score": self._clamp_score(keyword_match_score),
            "llm_relevance_score": self._clamp_score(llm_relevance_score) if llm_relevance_score is not None else None,
            "relevance_score": self._clamp_score(relevance_score),
        }

    def get_strategy_name(self) -> str:
        """Return the strategy name."""

        return "relevance"

    def _build_search_corpus(self, artifact: Artifact) -> str:
        """Build one normalized text blob from artifact fields used for topic matching."""

        parts = [
            artifact.title,
            artifact.abstract,
            artifact.summary_l1,
            " ".join(artifact.tags or []),
        ]
        return self._normalize_text(" ".join(part for part in parts if part))

    def _count_topic_matches(self, topics: list[str], search_corpus: str) -> int:
        """Count distinct normalized topics that occur in the search corpus."""

        if not search_corpus:
            return 0

        padded_corpus = f" {search_corpus} "
        normalized_topics = {
            normalized_topic
            for topic in topics
            if (normalized_topic := self._normalize_text(topic))
        }
        return sum(1 for topic in normalized_topics if f" {topic} " in padded_corpus)

    def _score_from_match_count(self, match_count: int) -> float:
        """Map preferred-topic hit count into the configured keyword score."""

        if match_count >= 4:
            return 1.0
        if match_count == 3:
            return 0.8
        if match_count == 2:
            return 0.6
        if match_count == 1:
            return 0.4
        return NO_MATCH_FLOOR_SCORE

    def _calculate_llm_relevance_score(self, artifact: Artifact, profile: Profile) -> float | None:
        """Return one precomputed LLM relevance score when available."""

        del profile
        if not artifact.score_breakdown:
            return None
        llm_score = artifact.score_breakdown.get("llm_relevance_score")
        if llm_score is None:
            return None
        try:
            return float(llm_score)
        except (TypeError, ValueError):
            return None

    def _merge_relevance_scores(self, keyword_match_score: float, llm_relevance_score: float | None) -> float:
        """Merge keyword and LLM relevance scores while LLM scoring remains optional."""

        if llm_relevance_score is None:
            return keyword_match_score
        return (keyword_match_score * KEYWORD_LLM_WEIGHT) + (llm_relevance_score * LLM_RELEVANCE_WEIGHT)

    def _normalize_text(self, value: str) -> str:
        """Lowercase text and normalize separators for stable topic matching."""

        normalized = value.lower().replace("-", " ").replace("_", " ")
        normalized = "".join(character if (character.isalnum() or character.isspace()) else " " for character in normalized)
        return re.sub(r"\s+", " ", normalized).strip()
