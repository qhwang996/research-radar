"""Pipeline for detecting research gaps between academic coverage and industry demand."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.models.research_gap import ResearchGap
from src.models.theme import Theme
from src.pipelines.base import BasePipeline
from src.repositories.research_gap_repository import ResearchGapRepository
from src.repositories.theme_repository import ThemeRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DemandTopic:
    """An aggregated industry demand topic with source evidence."""

    topic: str
    frequency: int
    sources: list[dict[str, Any]]  # [{artifact_id, problem_described, source_name}]
    solution_gaps: list[str]


@dataclass(slots=True)
class AcademicCoverage:
    """Academic coverage info for one topic."""

    topic: str
    matching_themes: list[str]  # theme_ids
    keyword_overlap_count: int


class GapDetectionPipeline(BasePipeline):
    """Cross-reference academic coverage against industry demand signals."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        gap_version: str = "v1",
        top_n: int = 10,
    ) -> None:
        """Initialize gap detection dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.gap_version = gap_version
        self.top_n = top_n

    def process(self, input_data: Any = None) -> list[ResearchGap]:
        """Run gap detection and persist results."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for gap detection pipeline")

        session = self.session_factory()
        try:
            # Step 1: Build academic coverage map from Themes
            themes = ThemeRepository(session).list_active_or_core()
            academic_keywords = self._build_academic_keyword_set(themes, session)

            # Step 2: Build industry demand map from blog demand signals
            demand_topics = self._build_demand_topics(session)

            if not demand_topics:
                logger.info("Gap detection skipped: no demand signals found")
                return []

            # Step 3: Compute coverage gaps (statistical)
            gap_candidates = self._compute_gaps(demand_topics, academic_keywords, themes)

            # Step 4: Persist top-N gaps
            week_id = self._current_week_id()
            gap_repo = ResearchGapRepository(session)
            gap_repo.delete_by_version(self.gap_version)

            saved: list[ResearchGap] = []
            for candidate in gap_candidates[: self.top_n]:
                gap = ResearchGap(
                    topic=candidate["topic"],
                    description=candidate.get("description"),
                    demand_signals=candidate["demand_signals"],
                    demand_frequency=candidate["demand_frequency"],
                    academic_coverage=candidate["academic_coverage"],
                    gap_score=candidate["gap_score"],
                    related_theme_ids=candidate["related_theme_ids"],
                    related_artifact_ids=candidate["related_artifact_ids"],
                    status="active",
                    generation_version=self.gap_version,
                    week_id=week_id,
                )
                saved.append(gap_repo.save(gap))

            logger.info(
                "Gap detection complete: %s demand topics, %s academic keywords, %s gaps saved",
                len(demand_topics),
                len(academic_keywords),
                len(saved),
            )
            return saved
        finally:
            session.close()

    def validate_input(self, data: Any) -> bool:
        return data is None

    def validate_output(self, data: Any) -> bool:
        return isinstance(data, list)

    def _build_academic_keyword_set(
        self,
        themes: list[Theme],
        session: Session,
    ) -> dict[str, list[str]]:
        """Build a mapping from normalized keyword → list of theme_ids.

        Collects keywords from Theme.keywords, Theme.methodology_tags,
        and related_concepts from paper L2 analyses.
        """

        keyword_to_themes: dict[str, list[str]] = {}

        for theme in themes:
            all_keywords: list[str] = []
            all_keywords.extend(theme.keywords or [])
            all_keywords.extend(theme.methodology_tags or [])

            # Extract related_concepts from papers' L2 analyses
            for artifact_id in (theme.artifact_ids or []):
                artifact = session.get(Artifact, artifact_id)
                if artifact and artifact.summary_l2:
                    try:
                        l2 = json.loads(artifact.summary_l2)
                        if isinstance(l2, dict):
                            all_keywords.extend(l2.get("related_concepts", []))
                    except json.JSONDecodeError:
                        pass

            for kw in all_keywords:
                norm = self._normalize_topic(kw)
                if norm:
                    keyword_to_themes.setdefault(norm, [])
                    if theme.theme_id not in keyword_to_themes[norm]:
                        keyword_to_themes[norm].append(theme.theme_id)

        return keyword_to_themes

    def _build_demand_topics(self, session: Session) -> list[DemandTopic]:
        """Aggregate demand signals from blog artifacts into topic counts."""

        statement = (
            select(Artifact)
            .where(Artifact.status == ArtifactStatus.ACTIVE)
            .where(Artifact.source_type == SourceType.BLOGS)
            .where(Artifact.summary_l2.is_not(None))
            .where(Artifact.summary_l2 != "")
        )
        blogs = list(session.scalars(statement))

        # Collect all related_academic_topics + solution_gaps
        topic_counter: Counter[str] = Counter()
        topic_sources: dict[str, list[dict[str, Any]]] = {}
        topic_gaps: dict[str, list[str]] = {}

        for blog in blogs:
            try:
                signal = json.loads(blog.summary_l2)
            except json.JSONDecodeError:
                continue
            if not isinstance(signal, dict) or signal.get("signal_type") != "demand":
                continue

            source_info = {
                "artifact_id": blog.id,
                "problem_described": signal.get("problem_described", ""),
                "source_name": blog.source_name or "Unknown",
            }

            for topic in signal.get("related_academic_topics", []):
                norm = self._normalize_topic(topic)
                if not norm:
                    continue
                topic_counter[norm] += 1
                topic_sources.setdefault(norm, []).append(source_info)
                for gap in signal.get("solution_gaps", []):
                    topic_gaps.setdefault(norm, [])
                    if gap not in topic_gaps[norm]:
                        topic_gaps[norm].append(gap)

        demand_topics = [
            DemandTopic(
                topic=topic,
                frequency=count,
                sources=topic_sources.get(topic, []),
                solution_gaps=topic_gaps.get(topic, []),
            )
            for topic, count in topic_counter.most_common()
        ]
        return demand_topics

    def _compute_gaps(
        self,
        demand_topics: list[DemandTopic],
        academic_keywords: dict[str, list[str]],
        themes: list[Theme],
    ) -> list[dict[str, Any]]:
        """Compute gap scores by cross-referencing demand against academic coverage."""

        total_academic_keywords = len(academic_keywords) if academic_keywords else 1
        gaps: list[dict[str, Any]] = []

        for dt in demand_topics:
            # Check how well this demand topic is covered academically
            matching_theme_ids: list[str] = []
            overlap_count = 0

            # Direct keyword match
            if dt.topic in academic_keywords:
                matching_theme_ids.extend(academic_keywords[dt.topic])
                overlap_count += 1

            # Fuzzy match: check if demand topic is a substring of any academic keyword or vice versa
            for ak, theme_ids in academic_keywords.items():
                if ak == dt.topic:
                    continue
                if dt.topic in ak or ak in dt.topic:
                    overlap_count += 1
                    for tid in theme_ids:
                        if tid not in matching_theme_ids:
                            matching_theme_ids.append(tid)

            # Coverage ratio: 0 = no coverage, 1 = well covered
            academic_coverage = min(1.0, overlap_count / 3.0)  # normalize: 3+ matches = fully covered

            # Gap score: high demand + low coverage = high gap
            gap_score = dt.frequency * (1.0 - academic_coverage)

            if gap_score <= 0:
                continue

            # Collect related artifact IDs
            related_artifact_ids = list({s["artifact_id"] for s in dt.sources})

            # Build description from solution gaps
            description = "; ".join(dt.solution_gaps[:3]) if dt.solution_gaps else None

            gaps.append({
                "topic": dt.topic,
                "description": description,
                "demand_signals": dt.sources[:5],  # cap at 5 sources for storage
                "demand_frequency": dt.frequency,
                "academic_coverage": round(academic_coverage, 3),
                "gap_score": round(gap_score, 3),
                "related_theme_ids": matching_theme_ids[:5],
                "related_artifact_ids": related_artifact_ids[:10],
            })

        # Sort by gap_score descending
        gaps.sort(key=lambda g: g["gap_score"], reverse=True)
        return gaps

    def _normalize_topic(self, topic: str) -> str:
        """Normalize a topic string for matching."""

        normalized = topic.lower().strip()
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _current_week_id(self) -> str:
        """Return the current ISO week id."""

        iso_year, iso_week, _ = date.today().isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
