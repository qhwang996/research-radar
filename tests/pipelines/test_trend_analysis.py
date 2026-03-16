"""Tests for the trend analysis pipeline."""

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
from src.models.enums import ArtifactStatus, SourceType, ThemeStatus
from src.models.theme import Theme
from src.pipelines.trend_analysis import TrendAnalysisPipeline
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.theme_repository import ThemeRepository


class StubLLMClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.lock = threading.Lock()

    def generate(self, prompt: str, **kwargs) -> str:
        with self.lock:
            self.calls.append({"prompt": prompt, **kwargs})
            if not self.responses:
                raise AssertionError("No queued response")
            response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)


def _trend_response() -> str:
    return json.dumps(
        {
            "methodology_tags": ["fuzzing", "symbolic execution", "taint analysis"],
            "open_questions": ["如何提高大规模系统的覆盖率？", "如何处理复杂的状态依赖？"],
            "methodology_evolution": "从纯黑盒 fuzzing 逐步过渡到结合程序分析的灰盒方法。",
        },
        ensure_ascii=False,
    )


class TrendAnalysisPipelineTestCase(unittest.TestCase):

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

    def test_computes_growing_trend(self) -> None:
        """Theme with increasing recent papers should be marked growing."""

        theme = self._save_theme(
            name="Growing Theme",
            paper_count_by_year={"2022": 2, "2023": 3, "2024": 5, "2025": 8},
        )

        llm_client = StubLLMClient([_trend_response()])
        pipeline = TrendAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            qualitative=False,
        )
        (self.workspace / "prompt.md").write_text("{{theme_name}}", encoding="utf-8")

        result = pipeline.process()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].trend_direction, "growing")

    def test_computes_declining_trend(self) -> None:
        """Theme with decreasing recent papers should be marked declining."""

        self._save_theme(
            name="Declining Theme",
            paper_count_by_year={"2022": 10, "2023": 8, "2024": 3, "2025": 1},
        )

        pipeline = TrendAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=StubLLMClient([]),
            qualitative=False,
        )

        result = pipeline.process()

        self.assertEqual(result[0].trend_direction, "declining")

    def test_qualitative_updates_methodology_tags(self) -> None:
        """LLM qualitative analysis should update methodology_tags and open_questions."""

        artifact = self._save_artifact_with_l2()
        theme = self._save_theme(
            name="Qualitative Theme",
            artifact_ids=[artifact.id],
            paper_count_by_year={"2024": 3, "2025": 3},
        )

        llm_client = StubLLMClient([_trend_response()])
        pipeline = TrendAnalysisPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            qualitative=True,
        )
        (self.workspace / "prompt.md").write_text(
            "{{theme_name}} {{paper_summaries}}", encoding="utf-8"
        )

        result = pipeline.process()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].methodology_tags, ["fuzzing", "symbolic execution", "taint analysis"])
        self.assertEqual(len(result[0].open_questions), 2)
        self.assertEqual(len(llm_client.calls), 1)

    def _save_theme(self, **kwargs) -> Theme:
        session: Session = self.session_factory()
        try:
            repo = ThemeRepository(session)
            return repo.save(
                Theme(
                    name=kwargs.pop("name", "Test Theme"),
                    keywords=kwargs.pop("keywords", ["web-security"]),
                    artifact_ids=kwargs.pop("artifact_ids", []),
                    artifact_count=kwargs.pop("artifact_count", 0),
                    paper_count_by_year=kwargs.pop("paper_count_by_year", {}),
                    status=kwargs.pop("status", ThemeStatus.CANDIDATE),
                    generation_version="v1",
                    week_id="2026-W11",
                    **kwargs,
                )
            )
        finally:
            session.close()

    def _save_artifact_with_l2(self) -> Artifact:
        session: Session = self.session_factory()
        try:
            repo = ArtifactRepository(session)
            return repo.save(
                Artifact(
                    title="Test Paper",
                    authors=["Author"],
                    year=2025,
                    source_type=SourceType.PAPERS,
                    source_tier="t1-conference",
                    source_name="NDSS",
                    source_url="https://example.com/paper",
                    summary_l2=json.dumps(
                        {
                            "research_problem": "Web 漏洞检测效率问题",
                            "methodology": "灰盒 fuzzing + 污点分析",
                        },
                        ensure_ascii=False,
                    ),
                    status=ArtifactStatus.ACTIVE,
                )
            )
        finally:
            session.close()
