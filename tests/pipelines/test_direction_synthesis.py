"""Tests for the direction synthesis pipeline."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.llm.base import ModelTier
from src.models.enums import DirectionStatus, ThemeStatus
from src.models.research_gap import ResearchGap
from src.models.theme import Theme
from src.pipelines.direction_synthesis import DirectionSynthesisPipeline
from src.repositories.candidate_direction_repository import CandidateDirectionRepository
from src.repositories.research_gap_repository import ResearchGapRepository
from src.repositories.theme_repository import ThemeRepository


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


def _synthesis_response() -> str:
    return json.dumps(
        [
            {
                "title": "SSRF 自动化检测框架",
                "description": "构建面向云原生环境的 SSRF 自动化检测和验证框架",
                "rationale": "工业界多个来源反映 SSRF 检测困难，学术界覆盖不足",
                "why_now": "云原生架构普及使 SSRF 攻击面扩大",
                "gap_topic": "ssrf detection",
                "novelty_score": 4,
                "impact_score": 5,
                "feasibility_score": 3,
                "barrier_score": 4,
                "open_questions": ["如何处理微服务间的复杂调用链？"],
                "key_evidence": ["多个安全博客报告 SSRF 问题"],
            }
        ],
        ensure_ascii=False,
    )


class DirectionSynthesisPipelineTestCase(unittest.TestCase):
    """Tests for gap-based research direction synthesis."""

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

    def test_synthesizes_direction_from_gaps(self) -> None:
        """Pipeline should create CandidateDirection records from active gaps."""

        self._save_gap(topic="ssrf detection", gap_score=3.0, demand_frequency=3)
        self._save_theme(name="Web Fuzzing")

        llm_client = StubLLMClient([_synthesis_response()])
        pipeline = DirectionSynthesisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{gaps}}\n{{themes}}", encoding="utf-8")

        result = pipeline.process()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "SSRF 自动化检测框架")
        self.assertEqual(result[0].status, DirectionStatus.ACTIVE)
        self.assertIsNotNone(result[0].composite_direction_score)
        self.assertIsNotNone(result[0].novelty_score)
        self.assertEqual(len(llm_client.calls), 1)
        self.assertEqual(llm_client.calls[0]["model_tier"], ModelTier.PREMIUM)

    def test_returns_empty_when_no_gaps(self) -> None:
        """Pipeline should skip when there are no active gaps."""

        llm_client = StubLLMClient([_synthesis_response()])
        pipeline = DirectionSynthesisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
        )

        result = pipeline.process()

        self.assertEqual(result, [])
        self.assertEqual(llm_client.calls, [])

    def test_score_normalization(self) -> None:
        """Raw 1-5 scores should be normalized to 0.0-1.0."""

        self._save_gap(topic="ssrf detection", gap_score=2.0, demand_frequency=2)

        llm_client = StubLLMClient([_synthesis_response()])
        pipeline = DirectionSynthesisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{gaps}}\n{{themes}}", encoding="utf-8")

        result = pipeline.process()

        self.assertEqual(len(result), 1)
        d = result[0]
        # novelty_score=4 -> (4-1)/4 = 0.75
        self.assertAlmostEqual(d.novelty_score, 0.75, places=2)
        # impact_score=5 -> (5-1)/4 = 1.0
        self.assertAlmostEqual(d.impact_score, 1.0, places=2)
        # feasibility_score=3 -> (3-1)/4 = 0.5
        self.assertAlmostEqual(d.feasibility_score, 0.5, places=2)
        # barrier_score=4 -> (4-1)/4 = 0.75
        self.assertAlmostEqual(d.barrier_score, 0.75, places=2)

    def _save_gap(self, **kwargs) -> ResearchGap:
        session: Session = self.session_factory()
        try:
            repo = ResearchGapRepository(session)
            return repo.save(
                ResearchGap(
                    topic=kwargs.pop("topic", "test gap"),
                    gap_score=kwargs.pop("gap_score", 1.0),
                    demand_frequency=kwargs.pop("demand_frequency", 1),
                    academic_coverage=kwargs.pop("academic_coverage", 0.0),
                    demand_signals=kwargs.pop("demand_signals", []),
                    related_theme_ids=kwargs.pop("related_theme_ids", []),
                    related_artifact_ids=kwargs.pop("related_artifact_ids", []),
                    status="active",
                    generation_version="v1",
                    week_id="2026-W11",
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_theme(self, **kwargs) -> Theme:
        session: Session = self.session_factory()
        try:
            repo = ThemeRepository(session)
            return repo.save(
                Theme(
                    name=kwargs.pop("name", "Test Theme"),
                    keywords=kwargs.pop("keywords", ["web-security"]),
                    artifact_ids=kwargs.pop("artifact_ids", []),
                    artifact_count=0,
                    status=ThemeStatus.CANDIDATE,
                    generation_version="v1",
                    week_id="2026-W11",
                    **kwargs,
                )
            )
        finally:
            session.close()
