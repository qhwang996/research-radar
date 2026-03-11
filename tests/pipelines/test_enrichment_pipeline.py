"""Tests for the enrichment pipeline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.exceptions import LLMError
from src.llm.base import ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.models.profile import Profile
from src.pipelines.enrichment import EnrichmentPipeline
from src.repositories.artifact_repository import ArtifactRepository


class StubLLMClient:
    """Tiny LLM stub with queued responses."""

    def __init__(self, responses: list[object]) -> None:
        """Store deterministic LLM outcomes."""

        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        prompt: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        cache_key: str | None = None,
    ) -> str:
        """Return the next queued response or raise the next queued error."""

        self.calls.append(
            {
                "prompt": prompt,
                "model_tier": model_tier,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "cache_key": cache_key,
            }
        )
        if not self.responses:
            raise AssertionError("No queued response in StubLLMClient")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)


class EnrichmentPipelineTestCase(unittest.TestCase):
    """Integration-style tests for artifact enrichment."""

    def setUp(self) -> None:
        """Create an isolated database and pipeline dependencies."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_process_enriches_active_artifacts_with_summary_and_tags(self) -> None:
        """Unenriched active artifacts should receive summary_l1 and tags."""

        llm_client = StubLLMClient(
            [
                '{"summary_l1": "A concise one-line summary.", "tags": ["browser-security", "side-channel"]}'
            ]
        )
        pipeline = EnrichmentPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{artifact_context}}", encoding="utf-8")
        artifact = self._save_artifact(title="Interesting Paper", abstract="Deep browser isolation work.")
        self._save_profile(interests=["browser security"], preferred_topics=["sandboxing"])

        enriched = pipeline.process(None)

        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0].summary_l1, "A concise one-line summary.")
        self.assertEqual(enriched[0].tags, ["browser-security", "side-channel"])
        self.assertEqual(len(llm_client.calls), 1)
        self.assertEqual(llm_client.calls[0]["model_tier"], ModelTier.FAST)
        self.assertTrue(str(llm_client.calls[0]["cache_key"]).startswith("enrichment_v1_"))
        self.assertIn("browser security", str(llm_client.calls[0]["prompt"]))

    def test_process_skips_artifacts_that_are_already_enriched(self) -> None:
        """Artifacts with summary and tags should not be sent to the LLM again."""

        llm_client = StubLLMClient(['{"summary_l1": "unused", "tags": ["unused"]}'])
        pipeline = EnrichmentPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{artifact_context}}", encoding="utf-8")
        self._save_artifact(
            title="Already Enriched",
            summary_l1="Existing summary.",
            tags=["existing-tag"],
        )

        enriched = pipeline.process(None)

        self.assertEqual(enriched, [])
        self.assertEqual(llm_client.calls, [])

    def test_process_continues_when_one_artifact_enrichment_fails(self) -> None:
        """One failed artifact should not prevent the rest from being enriched."""

        llm_client = StubLLMClient(
            [
                LLMError("temporary failure"),
                '{"summary_l1": "Second artifact summary.", "tags": ["network-security"]}',
            ]
        )
        pipeline = EnrichmentPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{artifact_context}}", encoding="utf-8")
        first = self._save_artifact(title="First Artifact")
        second = self._save_artifact(title="Second Artifact")

        enriched = pipeline.process(None)

        self.assertEqual([artifact.title for artifact in enriched], ["First Artifact"])

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            persisted_first = repository.get_by_id(first.id)
            persisted_second = repository.get_by_id(second.id)
            self.assertEqual(persisted_first.summary_l1, "Second artifact summary.")
            self.assertEqual(persisted_first.tags, ["network-security"])
            self.assertIsNone(persisted_second.summary_l1)
        finally:
            session.close()

    def test_process_can_target_specific_artifact_ids(self) -> None:
        """Targeted enrichment should only process the selected artifact ids."""

        llm_client = StubLLMClient(
            [
                '{"summary_l1": "Targeted summary.", "tags": ["program-analysis"]}',
            ]
        )
        pipeline = EnrichmentPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{artifact_context}}", encoding="utf-8")
        targeted = self._save_artifact(title="Targeted Artifact")
        untouched = self._save_artifact(title="Untouched Artifact")

        enriched = pipeline.process([targeted.id])

        self.assertEqual([artifact.id for artifact in enriched], [targeted.id])

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            self.assertEqual(repository.get_by_id(targeted.id).summary_l1, "Targeted summary.")
            self.assertIsNone(repository.get_by_id(untouched.id).summary_l1)
        finally:
            session.close()

    def test_process_salvages_summary_with_unescaped_quotes(self) -> None:
        """Malformed JSON with bare quotes inside summary_l1 should still be recovered."""

        llm_client = StubLLMClient(
            [
                """```json
{
  "summary_l1": "VETEOS is a static analysis tool for EOSIO contracts that detects "Groundhog Day" vulnerabilities.",
  "tags": ["eosio-smart-contracts", "static-analysis", "blockchain-security"]
}
```"""
            ]
        )
        pipeline = EnrichmentPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{artifact_context}}", encoding="utf-8")
        artifact = self._save_artifact(title="VETEOS")

        enriched = pipeline.process([artifact.id])

        self.assertEqual(len(enriched), 1)
        self.assertEqual(
            enriched[0].summary_l1,
            'VETEOS is a static analysis tool for EOSIO contracts that detects "Groundhog Day" vulnerabilities.',
        )
        self.assertEqual(
            enriched[0].tags,
            ["eosio-smart-contracts", "static-analysis", "blockchain-security"],
        )

    def _save_artifact(self, **kwargs) -> Artifact:
        """Persist one artifact with sensible defaults."""

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            return repository.save(
                Artifact(
                    title=kwargs.pop("title", "Test Artifact"),
                    authors=kwargs.pop("authors", ["Alice Example"]),
                    year=kwargs.pop("year", 2026),
                    source_type=kwargs.pop("source_type", SourceType.PAPERS),
                    source_tier=kwargs.pop("source_tier", "top-tier"),
                    source_name=kwargs.pop("source_name", "NDSS"),
                    source_url=kwargs.pop("source_url", "https://example.com/artifact"),
                    abstract=kwargs.pop("abstract", "A useful abstract."),
                    status=kwargs.pop("status", ArtifactStatus.ACTIVE),
                    summary_l1=kwargs.pop("summary_l1", None),
                    tags=kwargs.pop("tags", []),
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_profile(self, **kwargs) -> Profile:
        """Persist one active profile for prompt-context tests."""

        session: Session = self.session_factory()
        try:
            profile = Profile(
                profile_version=kwargs.pop("profile_version", "v1"),
                interests=kwargs.pop("interests", []),
                preferences=kwargs.pop("preferences", {}),
                preferred_topics=kwargs.pop("preferred_topics", []),
                is_active=kwargs.pop("is_active", True),
                **kwargs,
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile
        finally:
            session.close()
