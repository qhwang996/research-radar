"""Tests for the CandidateDirection model and repository."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.candidate_direction import CandidateDirection
from src.models.enums import DirectionStatus
from src.repositories.candidate_direction_repository import CandidateDirectionRepository


class CandidateDirectionRepositoryTestCase(unittest.TestCase):
    """Repository tests for candidate direction persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()
        self.repo = CandidateDirectionRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_save_and_retrieve(self) -> None:
        """Should persist and retrieve a direction by its business id."""

        direction = self.repo.save(self._build_direction(title="SSRF Framework"))
        fetched = self.repo.get_by_direction_id(direction.direction_id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "SSRF Framework")

    def test_list_active(self) -> None:
        """Should only return active directions."""

        self.repo.save(self._build_direction(title="Active", status=DirectionStatus.ACTIVE))
        self.repo.save(self._build_direction(title="Archived", status=DirectionStatus.ARCHIVED))

        active = self.repo.list_active()

        self.assertEqual([d.title for d in active], ["Active"])

    def test_list_by_week(self) -> None:
        """Should filter directions by ISO week."""

        self.repo.save(self._build_direction(title="W11", week_id="2026-W11"))
        self.repo.save(self._build_direction(title="W12", week_id="2026-W12"))

        w11 = self.repo.list_by_week("2026-W11")

        self.assertEqual([d.title for d in w11], ["W11"])

    def test_delete_by_version(self) -> None:
        """Should delete all directions for a given generation version."""

        self.repo.save(self._build_direction(title="V1", generation_version="v1"))
        self.repo.save(self._build_direction(title="V2", generation_version="v2"))

        deleted = self.repo.delete_by_version("v1")

        self.assertEqual(deleted, 1)
        self.assertEqual(len(self.repo.list_active()), 1)

    def test_scores_and_json_fields(self) -> None:
        """Scores and JSON list fields should persist correctly."""

        direction = self.repo.save(
            self._build_direction(
                title="Scored Direction",
                novelty_score=0.75,
                impact_score=1.0,
                feasibility_score=0.5,
                barrier_score=0.75,
                composite_direction_score=0.78,
                open_questions=["问题1", "问题2"],
                related_theme_ids=["theme-uuid-1"],
                supporting_artifact_ids=[1, 2, 3],
            )
        )

        fetched = self.repo.get_by_direction_id(direction.direction_id)

        self.assertAlmostEqual(fetched.novelty_score, 0.75)
        self.assertAlmostEqual(fetched.composite_direction_score, 0.78)
        self.assertEqual(fetched.open_questions, ["问题1", "问题2"])
        self.assertEqual(fetched.related_theme_ids, ["theme-uuid-1"])
        self.assertEqual(fetched.supporting_artifact_ids, [1, 2, 3])

    def _build_direction(self, **kwargs) -> CandidateDirection:
        return CandidateDirection(
            title=kwargs.pop("title", "Test Direction"),
            description=kwargs.pop("description", "A test direction."),
            rationale=kwargs.pop("rationale", "Because gaps exist."),
            why_now=kwargs.pop("why_now", "Timing is right."),
            status=kwargs.pop("status", DirectionStatus.ACTIVE),
            generation_version=kwargs.pop("generation_version", "v1"),
            week_id=kwargs.pop("week_id", "2026-W11"),
            **kwargs,
        )
