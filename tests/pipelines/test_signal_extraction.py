"""Tests for the signal extraction pipeline."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.llm.base import ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.pipelines.signal_extraction import SignalExtractionPipeline
from src.repositories.artifact_repository import ArtifactRepository


class StubLLMClient:
    """Tiny LLM stub with queued responses."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.lock = threading.Lock()

    def generate(self, prompt: str, **kwargs) -> str:
        with self.lock:
            self.calls.append({"prompt": prompt, **kwargs})
            if not self.responses:
                raise AssertionError("No queued response in StubLLMClient")
            response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)


def _signal_response() -> str:
    return json.dumps(
        {
            "signal_type": "demand",
            "problem_described": "Web 应用中的 SSRF 漏洞检测困难",
            "affected_systems": ["Web 应用", "云服务"],
            "current_solutions": "WAF 规则和手动审计",
            "solution_gaps": ["无法检测复杂的 SSRF 链", "缺少自动化验证"],
            "urgency_indicators": ["云原生架构普及增加攻击面"],
            "related_academic_topics": ["vulnerability detection", "web security", "program analysis"],
        },
        ensure_ascii=False,
    )


class SignalExtractionPipelineTestCase(unittest.TestCase):
    """Tests for blog demand signal extraction."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_extracts_signal_from_blog(self) -> None:
        """Pipeline should extract and persist a demand signal JSON for a blog artifact."""

        artifact = self._save_artifact(title="SSRF in Cloud", source_type=SourceType.BLOGS)
        llm_client = StubLLMClient([_signal_response()])
        pipeline = SignalExtractionPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}} {{content}} {{tags}}", encoding="utf-8")

        result = pipeline.process(artifact.id)

        self.assertEqual(len(result), 1)
        payload = json.loads(result[0].summary_l2)
        self.assertEqual(payload["signal_type"], "demand")
        self.assertIn("SSRF", payload["problem_described"])
        self.assertEqual(len(llm_client.calls), 1)

    def test_skips_papers(self) -> None:
        """Pipeline should not process paper artifacts."""

        self._save_artifact(title="Paper Artifact", source_type=SourceType.PAPERS)
        llm_client = StubLLMClient([_signal_response()])
        pipeline = SignalExtractionPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")

        result = pipeline.process(None)

        self.assertEqual(result, [])
        self.assertEqual(llm_client.calls, [])

    def test_skips_already_extracted(self) -> None:
        """Blog artifacts with existing demand signal should be skipped."""

        self._save_artifact(
            title="Already Done",
            source_type=SourceType.BLOGS,
            summary_l2=json.dumps({"signal_type": "demand", "problem_described": "existing"}),
        )
        llm_client = StubLLMClient([_signal_response()])
        pipeline = SignalExtractionPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")

        result = pipeline.process(None)

        self.assertEqual(result, [])
        self.assertEqual(llm_client.calls, [])

    def _save_artifact(self, **kwargs) -> Artifact:
        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            return repository.save(
                Artifact(
                    title=kwargs.pop("title", "Test Blog"),
                    authors=kwargs.pop("authors", ["Blogger"]),
                    year=kwargs.pop("year", 2026),
                    source_type=kwargs.pop("source_type", SourceType.BLOGS),
                    source_tier=kwargs.pop("source_tier", "t3-research-blog"),
                    source_name=kwargs.pop("source_name", "PortSwigger Research"),
                    source_url=kwargs.pop("source_url", "https://example.com/blog"),
                    abstract=kwargs.pop("abstract", "A security blog post."),
                    summary_l1=kwargs.pop("summary_l1", "博客文章关于 SSRF 检测。"),
                    summary_l2=kwargs.pop("summary_l2", None),
                    tags=kwargs.pop("tags", ["web-security"]),
                    relevance_score=kwargs.pop("relevance_score", 0.7),
                    status=kwargs.pop("status", ArtifactStatus.ACTIVE),
                    **kwargs,
                )
            )
        finally:
            session.close()
