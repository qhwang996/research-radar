"""Tests for repository CRUD helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, FeedbackTargetType, FeedbackType, RawFetchStatus, SourceType
from src.models.feedback import FeedbackEvent
from src.models.profile import Profile
from src.models.raw_fetch import RawFetch
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.feedback_repository import FeedbackRepository
from src.repositories.profile_repository import ProfileRepository
from src.repositories.raw_fetch_repository import RawFetchRepository


class RepositoryTestCase(unittest.TestCase):
    """Base test case that provisions an isolated SQLite database."""

    def setUp(self) -> None:
        """Create an isolated test database and repositories."""

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()

        self.artifacts = ArtifactRepository(self.session)
        self.feedback = FeedbackRepository(self.session)
        self.profiles = ProfileRepository(self.session)
        self.raw_fetches = RawFetchRepository(self.session)

    def tearDown(self) -> None:
        """Close the session and remove the temporary database."""

        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_artifact_repository_supports_crud(self) -> None:
        """Artifact repository should support create, read, update, and delete."""

        artifact = Artifact(
            title="Scored Artifact",
            authors=["Alice"],
            year=2026,
            source_type=SourceType.PAPERS,
            source_url="https://example.com/papers/scored",
            final_score=0.7,
        )

        saved = self.artifacts.save(artifact)
        fetched = self.artifacts.get_by_canonical_id(saved.canonical_id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Scored Artifact")

        fetched.final_score = 0.92
        fetched.status = ArtifactStatus.ARCHIVED
        updated = self.artifacts.save(fetched)

        self.assertEqual(updated.final_score, 0.92)
        self.assertEqual(self.artifacts.list_by_status(ArtifactStatus.ARCHIVED)[0].id, updated.id)

        self.artifacts.delete(updated)
        self.assertIsNone(self.artifacts.get_by_id(saved.id))

    def test_feedback_repository_lists_events_for_target(self) -> None:
        """Feedback repository should return target-scoped event history."""

        first = FeedbackEvent(
            target_type=FeedbackTargetType.ARTIFACT,
            target_id="artifact-1",
            feedback_type=FeedbackType.LIKE,
            content={"interested": True},
        )
        second = FeedbackEvent(
            target_type=FeedbackTargetType.ARTIFACT,
            target_id="artifact-1",
            feedback_type=FeedbackType.NOTE,
            content={"note": "Potential dissertation angle"},
        )

        self.feedback.save(first)
        self.feedback.save(second)

        records = self.feedback.list_for_target(
            FeedbackTargetType.ARTIFACT,
            "artifact-1",
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].feedback_type, FeedbackType.LIKE)
        self.assertEqual(records[1].content["note"], "Potential dissertation angle")

    def test_profile_repository_returns_latest_active_snapshot(self) -> None:
        """Profile repository should expose version and latest snapshot lookups."""

        inactive = Profile(
            profile_version="v1",
            interests=["fuzzing"],
            preferences={"weight": 0.4},
            is_active=False,
        )
        active = Profile(
            profile_version="v2",
            interests=["program analysis"],
            preferences={"weight": 0.9},
            is_active=True,
        )

        self.profiles.save(inactive)
        self.profiles.save(active)

        self.assertEqual(self.profiles.get_by_profile_version("v1").id, inactive.id)
        self.assertEqual(self.profiles.get_latest().id, active.id)
        self.assertEqual(self.profiles.get_latest_active().profile_version, "v2")

    def test_raw_fetch_repository_tracks_files_by_path_and_status(self) -> None:
        """RawFetch repository should support path lookups and status filtering."""

        first = RawFetch(
            file_path="/tmp/raw/first.json",
            content_hash="hash-1",
            source_type=SourceType.PAPERS,
            source_name="NDSS",
            item_count=1,
            processed_count=1,
            failed_count=0,
            status=RawFetchStatus.PROCESSED,
        )
        second = RawFetch(
            file_path="/tmp/raw/second.json",
            content_hash="hash-2",
            source_type=SourceType.BLOGS,
            source_name="PortSwigger Research",
            item_count=1,
            processed_count=0,
            failed_count=1,
            status=RawFetchStatus.FAILED,
        )

        self.raw_fetches.save(first)
        self.raw_fetches.save(second)

        fetched = self.raw_fetches.get_by_file_path("/tmp/raw/first.json")

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.content_hash, "hash-1")
        self.assertEqual(len(self.raw_fetches.list_by_status(RawFetchStatus.PROCESSED)), 1)
        self.assertEqual(self.raw_fetches.list_by_status(RawFetchStatus.FAILED)[0].file_path, second.file_path)
