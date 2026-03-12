"""Tests for profile CLI commands."""

from __future__ import annotations

import tempfile
import unittest

from click.testing import CliRunner
from sqlalchemy import select

from src.cli.main import cli
from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.profile import Profile


class ProfileCliTestCase(unittest.TestCase):
    """Integration tests for profile management commands."""

    def setUp(self) -> None:
        """Create an isolated database for each CLI test."""

        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite+pysqlite:///{self.temp_dir.name}/test.db"
        self.engine = create_database_engine(self.database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_seed_creates_profile(self) -> None:
        """profile seed should create one active profile from the seed file."""

        result = self.runner.invoke(cli, ["--database-url", self.database_url, "profile", "seed"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Seeded profile: v1-seed", result.output)

        session = self.session_factory()
        try:
            profiles = list(session.scalars(select(Profile)))
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0].profile_version, "v1-seed")
            self.assertTrue(profiles[0].is_active)
        finally:
            session.close()

    def test_seed_is_idempotent(self) -> None:
        """profile seed should skip when an active profile already exists."""

        session = self.session_factory()
        try:
            session.add(
                Profile(
                    profile_version="v-existing",
                    current_research_area="Existing Area",
                    interests=["existing"],
                    preferred_topics=["xss"],
                    avoided_topics=[],
                    is_active=True,
                )
            )
            session.commit()
        finally:
            session.close()

        result = self.runner.invoke(cli, ["--database-url", self.database_url, "profile", "seed"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Active profile already exists, skipping.", result.output)

        session = self.session_factory()
        try:
            profiles = list(session.scalars(select(Profile).order_by(Profile.id.asc())))
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0].profile_version, "v-existing")
        finally:
            session.close()
