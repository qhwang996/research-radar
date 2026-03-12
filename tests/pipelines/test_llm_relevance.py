"""Tests for the LLM relevance pipeline."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.exceptions import LLMError
from src.llm.base import ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.models.profile import Profile
from src.pipelines.llm_relevance import LLMRelevancePipeline
from src.repositories.artifact_repository import ArtifactRepository


class StubLLMClient:
    """Tiny LLM stub with queued responses."""

    def __init__(self, responses: list[object]) -> None:
        """Store deterministic LLM outcomes."""

        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.lock = threading.Lock()

    def generate(
        self,
        prompt: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        cache_key: str | None = None,
    ) -> str:
        """Return the next queued response or raise the next queued error."""

        with self.lock:
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


class LLMRelevancePipelineTestCase(unittest.TestCase):
    """Integration-style tests for LLM relevance scoring."""

    def setUp(self) -> None:
        """Create an isolated database and pipeline dependencies."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self._save_profile()

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_pipeline_stores_llm_relevance_in_breakdown(self) -> None:
        """Pipeline should persist the normalized LLM relevance score."""

        llm_client = StubLLMClient(['{"score": 4, "reason": "Highly related to web security."}'])
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("标题：{{title}}\n摘要：{{summary_l1}}\n标签：{{tags}}", encoding="utf-8")
        artifact = self._save_artifact(title="Relevant Artifact", summary_l1="A web fuzzing study.", tags=["web-fuzzing"])

        scored = pipeline.process([artifact.id])

        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0].score_breakdown["llm_relevance_score"], 0.8)
        self.assertEqual(scored[0].score_breakdown["llm_relevance_version"], "v2")
        self.assertEqual(len(llm_client.calls), 1)
        self.assertEqual(llm_client.calls[0]["model_tier"], ModelTier.STANDARD)
        self.assertTrue(str(llm_client.calls[0]["cache_key"]).startswith("relevance_v2_"))

    def test_pipeline_skips_already_scored(self) -> None:
        """Artifacts with existing llm_relevance_score should not be sent again."""

        llm_client = StubLLMClient(['{"score": 5, "reason": "unused"}'])
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        self._save_artifact(
            title="Already Scored",
            score_breakdown={"llm_relevance_score": 0.8, "llm_relevance_version": "v2"},
        )

        scored = pipeline.process(None)

        self.assertEqual(scored, [])
        self.assertEqual(llm_client.calls, [])

    def test_pipeline_rescores_on_version_mismatch(self) -> None:
        """Artifacts with an older relevance version should be rescored."""

        llm_client = StubLLMClient(['{"score": 5, "reason": "Directly relevant."}'])
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        artifact = self._save_artifact(
            title="Needs Rescore",
            score_breakdown={"llm_relevance_score": 0.2, "llm_relevance_version": "v1"},
        )

        scored = pipeline.process([artifact.id])

        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0].score_breakdown["llm_relevance_score"], 1.0)
        self.assertEqual(scored[0].score_breakdown["llm_relevance_version"], "v2")
        self.assertEqual(len(llm_client.calls), 1)

    def test_pipeline_continues_on_single_failure(self) -> None:
        """One failed artifact should not prevent other artifacts from being scored."""

        llm_client = StubLLMClient(
            [
                LLMError("temporary failure"),
                '{"score": 3, "reason": "Generally related."}',
            ]
        )
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        first = self._save_artifact(title="First Artifact")
        second = self._save_artifact(title="Second Artifact")

        scored = pipeline.process(None)

        self.assertEqual([artifact.title for artifact in scored], ["First Artifact"])

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            persisted_first = repository.get_by_id(first.id)
            persisted_second = repository.get_by_id(second.id)
            self.assertEqual(persisted_first.score_breakdown["llm_relevance_score"], 0.6)
            self.assertNotIn("llm_relevance_score", persisted_second.score_breakdown)
        finally:
            session.close()

    def test_score_mapping(self) -> None:
        """Raw 1-5 scores should map to the configured normalized values."""

        expected_scores = {1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0}

        for raw_score, normalized_score in expected_scores.items():
            with self.subTest(raw_score=raw_score):
                self.assertEqual(LLMRelevancePipeline.map_raw_score(raw_score), normalized_score)

    def test_parallel_processing(self) -> None:
        """Parallel relevance scoring should process multiple artifacts successfully."""

        llm_client = StubLLMClient(['{"score": 4, "reason": "Highly relevant."}'] * 4)
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            max_workers=2,
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        artifact_ids = [self._save_artifact(title=f"Artifact {index}").id for index in range(4)]

        scored = pipeline.process(artifact_ids)

        self.assertEqual(len(scored), 4)
        self.assertEqual(len(llm_client.calls), 4)

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            scores = [
                repository.get_by_id(artifact_id).score_breakdown.get("llm_relevance_score")
                for artifact_id in artifact_ids
            ]
            self.assertEqual(scores.count(0.8), 4)
        finally:
            session.close()

    def test_parallel_failure_isolation(self) -> None:
        """One parallel relevance failure should not block the rest."""

        llm_client = StubLLMClient(
            [
                LLMError("temporary failure"),
                '{"score": 5, "reason": "Directly relevant."}',
                '{"score": 5, "reason": "Directly relevant."}',
                '{"score": 5, "reason": "Directly relevant."}',
            ]
        )
        pipeline = LLMRelevancePipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            max_workers=2,
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        artifact_ids = [self._save_artifact(title=f"Failure Artifact {index}").id for index in range(4)]

        scored = pipeline.process(artifact_ids)

        self.assertEqual(len(scored), 3)
        self.assertEqual(len(llm_client.calls), 4)

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            persisted = [repository.get_by_id(artifact_id) for artifact_id in artifact_ids]
            scored_count = sum(
                1
                for artifact in persisted
                if artifact.score_breakdown.get("llm_relevance_score") == 1.0
            )
            missing_count = sum(
                1
                for artifact in persisted
                if artifact.score_breakdown.get("llm_relevance_score") is None
            )
            self.assertEqual(scored_count, 3)
            self.assertEqual(missing_count, 1)
        finally:
            session.close()

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
                    summary_l1=kwargs.pop("summary_l1", None),
                    tags=kwargs.pop("tags", []),
                    score_breakdown=kwargs.pop("score_breakdown", {}),
                    status=kwargs.pop("status", ArtifactStatus.ACTIVE),
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_profile(self) -> Profile:
        """Persist one active profile for LLM prompt context."""

        session: Session = self.session_factory()
        try:
            profile = Profile(
                profile_version="v1",
                current_research_area="Web应用安全与软件安全",
                interests=["Web漏洞检测", "程序分析"],
                preferred_topics=["web-security", "fuzzing"],
                avoided_topics=["blockchain"],
                is_active=True,
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile
        finally:
            session.close()
