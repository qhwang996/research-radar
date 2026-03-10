"""Tests for ORM model defaults and persistence."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, FeedbackTargetType, FeedbackType, RawFetchStatus, SourceType
from src.models.feedback import FeedbackEvent
from src.models.profile import Profile
from src.models.raw_fetch import RawFetch


class DatabaseTestCase(unittest.TestCase):
    """Base test case that provisions an isolated SQLite database."""

    def setUp(self) -> None:
        """Create an isolated test database and session."""

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.session: Session = self.session_factory()

    def tearDown(self) -> None:
        """Close the session and remove the temporary database."""

        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()


class ModelPersistenceTestCase(DatabaseTestCase):
    """Tests for core model persistence behavior."""

    def test_artifact_persists_defaults_and_scores(self) -> None:
        """Artifact should persist UUIDs, JSON fields, and timestamps."""

        artifact = Artifact(
            title="A Practical Security Paper",
            authors=["Alice", "Bob"],
            year=2026,
            source_type=SourceType.PAPERS,
            source_tier="top-tier",
            source_name="NDSS",
            source_url="https://example.com/papers/1",
            tags=["deserialization", "program-analysis"],
            external_ids={"doi": "10.1000/example"},
            recency_score=0.9,
            authority_score=0.95,
            relevance_score=0.8,
            final_score=0.88,
            score_breakdown={
                "recency_score": 0.9,
                "authority_score": 0.95,
                "relevance_score": 0.8,
            },
        )

        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)

        self.assertIsNotNone(artifact.id)
        self.assertTrue(artifact.canonical_id)
        self.assertEqual(artifact.status, ArtifactStatus.ACTIVE)
        self.assertEqual(artifact.authors, ["Alice", "Bob"])
        self.assertEqual(artifact.tags, ["deserialization", "program-analysis"])
        self.assertIsNotNone(artifact.created_at)
        self.assertIsNotNone(artifact.updated_at)

    def test_feedback_event_persists_append_only_payload(self) -> None:
        """Feedback events should persist stable IDs, timestamps, and JSON content."""

        feedback = FeedbackEvent(
            target_type=FeedbackTargetType.ARTIFACT,
            target_id="artifact-123",
            feedback_type=FeedbackType.LIKE,
            content={"interested": True, "note": "Worth tracking"},
        )

        self.session.add(feedback)
        self.session.commit()
        self.session.refresh(feedback)

        self.assertIsNotNone(feedback.id)
        self.assertTrue(feedback.event_id)
        self.assertEqual(feedback.content["note"], "Worth tracking")
        self.assertIsInstance(feedback.timestamp, datetime)

    def test_profile_snapshot_persists_interests_and_preferences(self) -> None:
        """Profile snapshots should persist versioned preference state."""

        profile = Profile(
            profile_version="v1",
            current_research_area="Systems Security",
            interests=["deserialization", "fuzzing"],
            preferences={"depth_over_breadth": True},
            primary_goals=["industrial impact", "academic rigor"],
            evaluation_criteria={"impact": ["real deployment potential"]},
            signal_sources_priority=["industry blogs", "top conferences"],
            preferred_topics=["supply chain security"],
            avoided_topics=["generic malware classification"],
            feedback_patterns={"likes": ["real-world pain points"]},
        )

        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)

        self.assertIsNotNone(profile.id)
        self.assertTrue(profile.profile_id)
        self.assertEqual(profile.interests, ["deserialization", "fuzzing"])
        self.assertTrue(profile.preferences["depth_over_breadth"])
        self.assertTrue(profile.is_active)

    def test_raw_fetch_persists_tracking_fields(self) -> None:
        """RawFetch should persist file tracking metadata and processing status."""

        raw_fetch = RawFetch(
            file_path="/tmp/raw/ndss_2026.json",
            content_hash="abc123",
            source_type=SourceType.PAPERS,
            source_name="NDSS",
            item_count=10,
            processed_count=10,
            failed_count=0,
            status=RawFetchStatus.PROCESSED,
            normalize_version="v1",
        )

        self.session.add(raw_fetch)
        self.session.commit()
        self.session.refresh(raw_fetch)

        self.assertIsNotNone(raw_fetch.id)
        self.assertEqual(raw_fetch.file_path, "/tmp/raw/ndss_2026.json")
        self.assertEqual(raw_fetch.status, RawFetchStatus.PROCESSED)
        self.assertEqual(raw_fetch.processed_count, 10)
        self.assertEqual(raw_fetch.normalize_version, "v1")
