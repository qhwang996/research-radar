"""Tests for the normalization pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.models.enums import SourceType
from src.pipelines.normalization import NormalizationPipeline
from src.repositories.artifact_repository import ArtifactRepository


class NormalizationPipelineTestCase(unittest.TestCase):
    """Integration-style tests for the normalization pipeline."""

    def setUp(self) -> None:
        """Create an isolated database and working directory for tests."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.pipeline = NormalizationPipeline(
            session_factory=self.session_factory,
            engine=self.engine,
            normalize_version="test-v1",
        )

    def tearDown(self) -> None:
        """Dispose resources created for the test."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_process_legacy_paper_payload_creates_artifact(self) -> None:
        """Legacy paper payloads should normalize into persisted artifacts."""

        raw_path = self._write_json(
            "legacy_ndss.json",
            {
                "source": "NDSS",
                "fetched_at": "2026-03-10T08:00:00+00:00",
                "url": "https://www.ndss-symposium.org/ndss2025/accepted-papers/",
                "papers": [
                    {
                        "title": "Example NDSS Paper",
                        "authors": ["Alice Example", "Bob Example"],
                        "paper_url": "https://www.ndss-symposium.org/ndss-paper/example-ndss-paper/",
                        "conference": "NDSS 2025",
                        "year": 2025,
                        "source_url": "https://www.ndss-symposium.org/ndss2025/accepted-papers/",
                    }
                ],
            },
        )

        artifacts = self.pipeline.process(raw_path)

        self.assertEqual(len(artifacts), 1)
        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            saved = repository.list_all()
            self.assertEqual(len(saved), 1)
            artifact = saved[0]
            self.assertEqual(artifact.title, "Example NDSS Paper")
            self.assertEqual(artifact.source_type, SourceType.PAPERS)
            self.assertEqual(
                artifact.source_url,
                "https://www.ndss-symposium.org/ndss-paper/example-ndss-paper/",
            )
            self.assertEqual(
                artifact.paper_url,
                "https://www.ndss-symposium.org/ndss-paper/example-ndss-paper/",
            )
            self.assertEqual(
                artifact.external_ids["listing_url"],
                "https://www.ndss-symposium.org/ndss2025/accepted-papers/",
            )
            self.assertEqual(artifact.normalize_version, "test-v1")
            self.assertEqual(artifact.raw_content_path, str(raw_path.resolve()))
        finally:
            session.close()

    def test_process_directory_deduplicates_by_stable_canonical_id(self) -> None:
        """Reprocessing duplicate titles should update an existing artifact instead of duplicating it."""

        raw_dir = self.workspace / "raw"
        raw_dir.mkdir()
        self._write_json(
            raw_dir / "first.json",
            {
                "source": "IEEE S&P",
                "fetched_at": "2026-03-10T09:00:00+00:00",
                "papers": [
                    {
                        "title": "Duplicate Title Paper",
                        "authors": [],
                        "conference": "IEEE S&P 2026",
                        "year": 2026,
                        "source_url": "https://sp2026.ieee-security.org/accepted-papers.html",
                    }
                ],
            },
        )
        self._write_json(
            raw_dir / "second.json",
            {
                "source": "IEEE S&P",
                "fetched_at": "2026-03-10T10:00:00+00:00",
                "items": [
                    {
                        "title": "Duplicate Title Paper",
                        "authors": ["Alice Example", "Bob Example"],
                        "abstract": "A richer abstract from the second crawl.",
                        "paper_url": "https://sp2026.ieee-security.org/papers/duplicate-title-paper.html",
                        "conference": "IEEE S&P 2026",
                        "year": 2026,
                        "source_type": "papers",
                        "source_url": "https://sp2026.ieee-security.org/accepted-papers.html",
                    }
                ],
            },
        )

        artifacts = self.pipeline.process(raw_dir)

        self.assertEqual(len(artifacts), 2)
        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            saved = repository.list_all()
            self.assertEqual(len(saved), 1)
            artifact = saved[0]
            self.assertEqual(artifact.authors, ["Alice Example", "Bob Example"])
            self.assertEqual(artifact.abstract, "A richer abstract from the second crawl.")
            self.assertEqual(
                artifact.paper_url,
                "https://sp2026.ieee-security.org/papers/duplicate-title-paper.html",
            )
        finally:
            session.close()

    def test_process_blog_payload_maps_article_url_and_publication_date(self) -> None:
        """Blog payloads should normalize into blog artifacts with content URLs."""

        raw_path = self._write_json(
            "portswigger_blog.json",
            {
                "source": "PortSwigger Research",
                "source_type": "blogs",
                "fetched_at": "2026-03-10T11:00:00+00:00",
                "items": [
                    {
                        "title": "HTTP Desync Attacks Revisited",
                        "authors": ["PortSwigger Research"],
                        "article_url": "https://portswigger.net/research/http-desync-attacks-revisited",
                        "source_url": "https://portswigger.net/research/articles",
                        "published_at": "2026-03-05",
                        "excerpt": "New exploitation techniques for request smuggling.",
                        "tags": ["web-security", "http"],
                    }
                ],
            },
        )

        self.pipeline.process(raw_path)

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            saved = repository.list_all()
            self.assertEqual(len(saved), 1)
            artifact = saved[0]
            self.assertEqual(artifact.source_type, SourceType.BLOGS)
            self.assertEqual(
                artifact.source_url,
                "https://portswigger.net/research/http-desync-attacks-revisited",
            )
            self.assertIsNone(artifact.paper_url)
            self.assertEqual(artifact.year, 2026)
            self.assertEqual(artifact.abstract, "New exploitation techniques for request smuggling.")
            self.assertEqual(artifact.tags, ["web-security", "http"])
        finally:
            session.close()

    def _write_json(self, path: str | Path, payload: dict[str, object]) -> Path:
        """Write a JSON payload into the temporary workspace."""

        target = self.workspace / path if isinstance(path, str) else path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target.resolve()
