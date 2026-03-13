"""Tests for feedback collection via CLI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner
from sqlalchemy.orm import Session

from src.cli.main import cli
from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.artifact import Artifact
from src.models.enums import FeedbackTargetType, FeedbackType, SourceType
from src.repositories.feedback_repository import FeedbackRepository


class FeedbackCliTestCase(unittest.TestCase):
    """End-to-end feedback CLI tests."""

    def setUp(self) -> None:
        """Create an isolated database and CLI runner."""

        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.database_path = self.workspace / "test.db"
        self.database_url = f"sqlite+pysqlite:///{self.database_path}"
        self.engine = create_database_engine(self.database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self) -> None:
        """Dispose resources created for tests."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_feedback_like_creates_event(self) -> None:
        """A like feedback should create one append-only feedback event."""

        artifact = self._save_artifact("Artifact Like")

        result = self.runner.invoke(
            cli,
            ["--database-url", self.database_url, "feedback", "--artifact-id", str(artifact.id), "--type", "like"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        events = self._list_feedback_events(str(artifact.id))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].target_type, FeedbackTargetType.ARTIFACT)
        self.assertEqual(events[0].feedback_type, FeedbackType.LIKE)
        self.assertEqual(events[0].content["type"], "like")

    def test_feedback_dislike_creates_event(self) -> None:
        """A dislike feedback should persist normally."""

        artifact = self._save_artifact("Artifact Dislike")

        result = self.runner.invoke(
            cli,
            [
                "--database-url",
                self.database_url,
                "feedback",
                "--artifact-id",
                str(artifact.id),
                "--type",
                "dislike",
                "--note",
                "Not relevant",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        event = self._list_feedback_events(str(artifact.id))[0]
        self.assertEqual(event.feedback_type, FeedbackType.DISLIKE)
        self.assertEqual(event.content["type"], "dislike")
        self.assertEqual(event.content["note"], "Not relevant")

    def test_feedback_read_creates_event_without_note(self) -> None:
        """A read feedback should persist without requiring note text."""

        artifact = self._save_artifact("Artifact Read")

        result = self.runner.invoke(
            cli,
            ["--database-url", self.database_url, "feedback", "--artifact-id", str(artifact.id), "--type", "read"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        event = self._list_feedback_events(str(artifact.id))[0]
        self.assertEqual(event.feedback_type, FeedbackType.READ)
        self.assertEqual(event.content["type"], "read")
        self.assertNotIn("note", event.content)

    def test_feedback_read_accepts_optional_note(self) -> None:
        """A read feedback may include an optional note."""

        artifact = self._save_artifact("Artifact Read Note")

        result = self.runner.invoke(
            cli,
            [
                "--database-url",
                self.database_url,
                "feedback",
                "--artifact-id",
                str(artifact.id),
                "--type",
                "read",
                "--note",
                "好文",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        event = self._list_feedback_events(str(artifact.id))[0]
        self.assertEqual(event.feedback_type, FeedbackType.READ)
        self.assertEqual(event.content["type"], "read")
        self.assertEqual(event.content["note"], "好文")

    def test_feedback_note_requires_text(self) -> None:
        """A note feedback without --note should fail validation."""

        artifact = self._save_artifact("Artifact Note")

        result = self.runner.invoke(
            cli,
            ["--database-url", self.database_url, "feedback", "--artifact-id", str(artifact.id), "--type", "note"],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--note is required", result.output)

    def test_feedback_invalid_artifact_id(self) -> None:
        """Feedback on a missing artifact should fail gracefully."""

        result = self.runner.invoke(
            cli,
            ["--database-url", self.database_url, "feedback", "--artifact-id", "999", "--type", "like"],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Artifact not found: 999", result.output)

    def test_feedback_events_are_append_only(self) -> None:
        """Multiple feedbacks on the same artifact should all persist."""

        artifact = self._save_artifact("Artifact Append")

        first = self.runner.invoke(
            cli,
            ["--database-url", self.database_url, "feedback", "--artifact-id", str(artifact.id), "--type", "like"],
        )
        second = self.runner.invoke(
            cli,
            [
                "--database-url",
                self.database_url,
                "feedback",
                "--artifact-id",
                str(artifact.id),
                "--type",
                "note",
                "--note",
                "Compare against prior work",
            ],
        )

        self.assertEqual(first.exit_code, 0, first.output)
        self.assertEqual(second.exit_code, 0, second.output)

        events = self._list_feedback_events(str(artifact.id))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].feedback_type, FeedbackType.LIKE)
        self.assertEqual(events[1].feedback_type, FeedbackType.NOTE)

    def _save_artifact(self, title: str) -> Artifact:
        """Persist one artifact for feedback tests."""

        session: Session = self.session_factory()
        try:
            artifact = Artifact(
                title=title,
                authors=["Alice Example"],
                year=2026,
                source_type=SourceType.PAPERS,
                source_tier="top-tier",
                source_name="NDSS",
                source_url=f"https://example.com/{title.lower().replace(' ', '-')}",
            )
            session.add(artifact)
            session.commit()
            session.refresh(artifact)
            return artifact
        finally:
            session.close()

    def _list_feedback_events(self, artifact_id: str):
        """Load persisted feedback events for one artifact."""

        session: Session = self.session_factory()
        try:
            return FeedbackRepository(session).list_for_target(FeedbackTargetType.ARTIFACT, artifact_id)
        finally:
            session.close()
