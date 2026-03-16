"""Tests for the ResearchGap model and repository."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.research_gap import ResearchGap
from src.repositories.research_gap_repository import ResearchGapRepository


class ResearchGapRepositoryTestCase(unittest.TestCase):
    """Repository tests for research gap persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()
        self.repo = ResearchGapRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_save_and_retrieve(self) -> None:
        """Should persist and retrieve a gap by its business id."""

        gap = self.repo.save(self._build_gap(topic="SSRF Detection"))
        fetched = self.repo.get_by_gap_id(gap.gap_id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.topic, "SSRF Detection")
        self.assertEqual(fetched.gap_score, 2.5)

    def test_list_active(self) -> None:
        """Should only return active gaps ordered by score descending."""

        self.repo.save(self._build_gap(topic="Low Score", gap_score=1.0))
        self.repo.save(self._build_gap(topic="High Score", gap_score=5.0))
        self.repo.save(self._build_gap(topic="Dismissed", gap_score=3.0, status="dismissed"))

        active = self.repo.list_active()

        self.assertEqual([g.topic for g in active], ["High Score", "Low Score"])

    def test_list_by_week(self) -> None:
        """Should filter gaps by ISO week."""

        self.repo.save(self._build_gap(topic="W11", week_id="2026-W11"))
        self.repo.save(self._build_gap(topic="W12", week_id="2026-W12"))

        w11_gaps = self.repo.list_by_week("2026-W11")

        self.assertEqual([g.topic for g in w11_gaps], ["W11"])

    def test_delete_by_version(self) -> None:
        """Should delete all gaps for a given generation version."""

        self.repo.save(self._build_gap(topic="V1 Gap", generation_version="v1"))
        self.repo.save(self._build_gap(topic="V2 Gap", generation_version="v2"))

        deleted = self.repo.delete_by_version("v1")

        self.assertEqual(deleted, 1)
        self.assertEqual(len(self.repo.list_active()), 1)
        self.assertEqual(self.repo.list_active()[0].topic, "V2 Gap")

    def test_json_fields_persist(self) -> None:
        """JSON fields like demand_signals and related_theme_ids should round-trip."""

        signals = [{"artifact_id": 1, "problem_described": "test", "source_name": "Blog"}]
        theme_ids = ["uuid-1", "uuid-2"]
        gap = self.repo.save(
            self._build_gap(
                topic="JSON Test",
                demand_signals=signals,
                related_theme_ids=theme_ids,
                related_artifact_ids=[10, 20],
            )
        )

        fetched = self.repo.get_by_gap_id(gap.gap_id)

        self.assertEqual(fetched.demand_signals, signals)
        self.assertEqual(fetched.related_theme_ids, theme_ids)
        self.assertEqual(fetched.related_artifact_ids, [10, 20])

    def _build_gap(self, **kwargs) -> ResearchGap:
        return ResearchGap(
            topic=kwargs.pop("topic", "Test Gap"),
            gap_score=kwargs.pop("gap_score", 2.5),
            demand_frequency=kwargs.pop("demand_frequency", 2),
            academic_coverage=kwargs.pop("academic_coverage", 0.1),
            demand_signals=kwargs.pop("demand_signals", []),
            related_theme_ids=kwargs.pop("related_theme_ids", []),
            related_artifact_ids=kwargs.pop("related_artifact_ids", []),
            status=kwargs.pop("status", "active"),
            generation_version=kwargs.pop("generation_version", "v1"),
            week_id=kwargs.pop("week_id", "2026-W11"),
            **kwargs,
        )
