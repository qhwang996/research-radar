"""Tests for the deep analysis pipeline."""

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
from src.models.profile import Profile
from src.pipelines.deep_analysis import DeepAnalysisPipeline
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


class DeepAnalysisPipelineTestCase(unittest.TestCase):
    """Integration-style tests for deep analysis generation."""

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

    def test_pipeline_stores_l2_analysis(self) -> None:
        """Pipeline should persist one JSON string with all required fields."""

        llm_client = StubLLMClient([self._analysis_response("Structured Paper")])
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text(
            "方向：{{research_area}}\n兴趣：{{interests}}\n标题：{{title}}\n摘要：{{abstract}}\n总结：{{summary_l1}}\n标签：{{tags}}",
            encoding="utf-8",
        )
        artifact = self._save_artifact(title="Structured Paper")

        analyzed = pipeline.process(None)

        self.assertEqual(len(analyzed), 1)
        payload = json.loads(analyzed[0].summary_l2 or "{}")
        self.assertEqual(
            set(payload.keys()),
            {
                "research_problem",
                "motivation",
                "methodology",
                "core_contributions",
                "limitations",
                "open_questions",
                "related_concepts",
            },
        )
        self.assertEqual(payload["research_problem"], "Structured Paper 要解决服务端 Web 漏洞检测效率不足的问题。")
        self.assertEqual(len(llm_client.calls), 1)
        self.assertEqual(llm_client.calls[0]["model_tier"], ModelTier.STANDARD)
        self.assertEqual(llm_client.calls[0]["max_tokens"], 1500)
        self.assertEqual(llm_client.calls[0]["temperature"], 0.3)
        self.assertTrue(str(llm_client.calls[0]["cache_key"]).startswith("deep_analysis_v1_"))
        self.assertIn("Web应用安全与软件安全", str(llm_client.calls[0]["prompt"]))
        self.assertIn("Structured Paper", str(llm_client.calls[0]["prompt"]))
        self.assertEqual(analyzed[0].id, artifact.id)

    def test_pipeline_skips_already_analyzed(self) -> None:
        """Artifacts with summary_l2 should not be sent to the LLM again."""

        llm_client = StubLLMClient([self._analysis_response("unused")])
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        self._save_artifact(title="Already Analyzed", summary_l2='{"existing":"value"}')

        analyzed = pipeline.process(None)

        self.assertEqual(analyzed, [])
        self.assertEqual(llm_client.calls, [])

    def test_pipeline_skips_low_relevance(self) -> None:
        """Artifacts below the relevance threshold should be skipped."""

        llm_client = StubLLMClient([self._analysis_response("unused")])
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        artifact = self._save_artifact(title="Low Relevance", relevance_score=0.59)

        analyzed = pipeline.process(None)

        self.assertEqual(analyzed, [])
        self.assertEqual(llm_client.calls, [])

        session: Session = self.session_factory()
        try:
            self.assertIsNone(ArtifactRepository(session).get_by_id(artifact.id).summary_l2)
        finally:
            session.close()

    def test_pipeline_skips_non_papers(self) -> None:
        """Non-paper artifacts should never be deep analyzed."""

        llm_client = StubLLMClient([self._analysis_response("unused")])
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        self._save_artifact(title="Blog Artifact", source_type=SourceType.BLOGS, relevance_score=0.95)

        analyzed = pipeline.process(None)

        self.assertEqual(analyzed, [])
        self.assertEqual(llm_client.calls, [])

    def test_pipeline_continues_on_single_failure(self) -> None:
        """One malformed LLM response should not block the remaining artifacts."""

        llm_client = StubLLMClient(
            [
                self._analysis_response("First Artifact"),
                "not-json",
                self._analysis_response("Third Artifact"),
            ]
        )
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            max_workers=1,
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        first = self._save_artifact(title="First Artifact")
        second = self._save_artifact(title="Second Artifact")
        third = self._save_artifact(title="Third Artifact")

        analyzed = pipeline.process([first.id, second.id, third.id])

        self.assertEqual([artifact.title for artifact in analyzed], ["First Artifact", "Third Artifact"])

        session: Session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            self.assertIsNotNone(repository.get_by_id(first.id).summary_l2)
            self.assertIsNone(repository.get_by_id(second.id).summary_l2)
            self.assertIsNotNone(repository.get_by_id(third.id).summary_l2)
        finally:
            session.close()

    def test_pipeline_forced_by_artifact_id(self) -> None:
        """Directly targeted artifact ids should bypass the relevance threshold."""

        llm_client = StubLLMClient([self._analysis_response("Forced Artifact")])
        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{title}}", encoding="utf-8")
        artifact = self._save_artifact(title="Forced Artifact", relevance_score=0.2)

        analyzed = pipeline.process(artifact.id)

        self.assertEqual([item.id for item in analyzed], [artifact.id])
        self.assertEqual(len(llm_client.calls), 1)

    def test_parse_response_with_code_fences(self) -> None:
        """Parser should recover a JSON payload wrapped in fenced markdown."""

        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=StubLLMClient([]),
            prompt_template_path=self.workspace / "prompt.md",
        )

        payload = pipeline._parse_analysis_response(
            f"```json\n{self._analysis_response('Fenced Paper')}\n```"
        )

        self.assertEqual(payload.research_problem, "Fenced Paper 要解决服务端 Web 漏洞检测效率不足的问题。")
        self.assertEqual(payload.limitations[0], "评估场景主要集中在公开基准，真实复杂业务覆盖有限。")

    def test_parse_response_missing_fields_degrades(self) -> None:
        """Missing optional fields should degrade to empty values instead of raising."""

        pipeline = DeepAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=StubLLMClient([]),
            prompt_template_path=self.workspace / "prompt.md",
        )

        payload = pipeline._parse_analysis_response(
            json.dumps(
                {
                    "research_problem": "问题",
                    "motivation": "动机",
                    "methodology": "方法",
                    "core_contributions": ["贡献"],
                    "open_questions": ["问题1"],
                    "related_concepts": ["概念1", "概念2"],
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(payload.limitations, [])
        self.assertEqual(payload.core_contributions, ["贡献"])
        self.assertEqual(payload.open_questions, ["问题1"])

    def _analysis_response(self, title: str) -> str:
        """Build one deterministic deep-analysis JSON payload."""

        return json.dumps(
            {
                "research_problem": f"{title} 要解决服务端 Web 漏洞检测效率不足的问题。",
                "motivation": "现有方法对复杂状态流和真实部署环境覆盖不足，导致高价值漏洞容易漏报。",
                "methodology": "结合程序分析、定向 fuzzing 和语义约束建模来缩小搜索空间并验证漏洞。",
                "core_contributions": ["提出面向 Web 攻击面的分析框架", "在公开数据集上验证了检测效果"],
                "limitations": ["评估场景主要集中在公开基准，真实复杂业务覆盖有限。"],
                "open_questions": ["如何把方法迁移到大规模生产系统并控制成本？"],
                "related_concepts": ["web fuzzing", "program analysis", "taint tracking"],
            },
            ensure_ascii=False,
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
                    summary_l1=kwargs.pop("summary_l1", "一篇关于 Web 安全分析的论文。"),
                    summary_l2=kwargs.pop("summary_l2", None),
                    tags=kwargs.pop("tags", ["web-security", "fuzzing"]),
                    relevance_score=kwargs.pop("relevance_score", 0.8),
                    status=kwargs.pop("status", ArtifactStatus.ACTIVE),
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_profile(self) -> Profile:
        """Persist one active profile for prompt-context tests."""

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
