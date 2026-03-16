"""Pipeline for computing trend statistics and qualitative analysis per Theme."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.theme import Theme
from src.pipelines.base import BasePipeline
from src.repositories.theme_repository import ThemeRepository

logger = logging.getLogger(__name__)

DEFAULT_TREND_PROMPT = """你是一位安全研究领域分析专家。请分析以下研究子领域的方法论演进和开放问题。

研究子领域：{{theme_name}}
描述：{{theme_description}}
关键词：{{theme_keywords}}
论文数量：{{paper_count}}

以下是该子领域中论文的研究问题和方法摘要：

{{paper_summaries}}

请返回一个 JSON，不要加 Markdown 代码块：

{
  "methodology_tags": ["该领域常用的研究方法1", "方法2", "方法3"],
  "open_questions": ["该领域尚待解决的关键问题1", "问题2", "问题3"],
  "methodology_evolution": "方法论演进的一句话总结"
}

要求：
- methodology_tags 列出 3-5 个该子领域的代表性研究方法
- open_questions 列出 2-4 个从多篇论文中归纳出的共性开放问题
- 使用中文
"""


class TrendAnalysisPipeline(BasePipeline):
    """Compute trend statistics and optional qualitative analysis for Themes."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        trend_version: str = "v1",
        qualitative: bool = True,
    ) -> None:
        """Initialize trend analysis dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/analyze_theme_trend.md")
        self.trend_version = trend_version
        self.qualitative = qualitative

    def process(self, input_data: Any = None) -> list[Theme]:
        """Compute trends for all active/core themes."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for trend analysis pipeline")

        session = self.session_factory()
        try:
            theme_repo = ThemeRepository(session)

            if isinstance(input_data, str):
                theme = theme_repo.get_by_theme_id(input_data)
                themes = [theme] if theme else []
            else:
                themes = theme_repo.list_active_or_core()

            if not themes:
                logger.info("Trend analysis skipped: no active themes")
                return []

            template = self._load_prompt_template()
            updated: list[Theme] = []

            for theme in themes:
                # Step 1: Quantitative trend (pure computation)
                trend_direction = self._compute_trend_direction(theme)
                theme.trend_direction = trend_direction

                # Step 2: Qualitative analysis (optional LLM)
                if self.qualitative:
                    self._run_qualitative_analysis(session, theme, template)

                updated.append(theme_repo.save(theme))

            logger.info("Trend analysis complete: %s themes updated", len(updated))
            return updated
        finally:
            session.close()

    def validate_input(self, data: Any) -> bool:
        return data is None or isinstance(data, str)

    def validate_output(self, data: Any) -> bool:
        return isinstance(data, list)

    def _compute_trend_direction(self, theme: Theme) -> str:
        """Determine trend direction from paper_count_by_year."""

        counts = theme.paper_count_by_year or {}
        if not counts:
            return "stable"

        sorted_years = sorted(counts.keys())
        if len(sorted_years) < 2:
            return "stable"

        # Compare recent 2 years vs older 2 years
        all_years = [int(y) for y in sorted_years]
        mid = max(all_years) - 1  # split point

        recent = sum(counts.get(str(y), 0) for y in all_years if y >= mid)
        older = sum(counts.get(str(y), 0) for y in all_years if y < mid)

        if recent > older * 1.3:
            return "growing"
        if recent < older * 0.7:
            return "declining"
        return "stable"

    def _run_qualitative_analysis(
        self,
        session: Session,
        theme: Theme,
        template: str,
    ) -> None:
        """Run LLM-based qualitative analysis for one theme."""

        paper_summaries = self._collect_paper_summaries(session, theme)
        if not paper_summaries:
            return

        prompt = self._build_prompt(template, theme, paper_summaries)
        cache_key = f"trend_{self.trend_version}_{theme.theme_id}"

        try:
            response_text = self.llm_client.generate(
                prompt,
                model_tier=ModelTier.STANDARD,
                max_tokens=1000,
                temperature=0.3,
                cache_key=cache_key,
            )
            payload = self._parse_response(response_text)

            if payload.get("methodology_tags"):
                theme.methodology_tags = payload["methodology_tags"]
            if payload.get("open_questions"):
                theme.open_questions = payload["open_questions"]

        except Exception as exc:
            logger.warning("Qualitative analysis failed for theme %s: %s", theme.name, exc)

    def _collect_paper_summaries(self, session: Session, theme: Theme) -> str:
        """Collect L2 summaries from theme's papers."""

        blocks: list[str] = []
        for artifact_id in (theme.artifact_ids or [])[:20]:  # cap at 20
            artifact = session.get(Artifact, artifact_id)
            if not artifact or not artifact.summary_l2:
                continue
            try:
                l2 = json.loads(artifact.summary_l2)
                if isinstance(l2, dict) and l2.get("research_problem"):
                    blocks.append(
                        f"- [{artifact.title}] 问题: {l2['research_problem']} "
                        f"方法: {l2.get('methodology', 'N/A')}"
                    )
            except json.JSONDecodeError:
                continue
        return "\n".join(blocks)

    def _build_prompt(self, template: str, theme: Theme, paper_summaries: str) -> str:
        """Render the trend analysis prompt."""

        replacements = {
            "{{theme_name}}": theme.name,
            "{{theme_description}}": theme.description or "N/A",
            "{{theme_keywords}}": ", ".join(theme.keywords or []),
            "{{paper_count}}": str(theme.artifact_count),
            "{{paper_summaries}}": paper_summaries,
        }
        prompt = template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM trend analysis response."""

        cleaned = self._extract_json_payload(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Trend analysis response is not valid JSON: {response_text}") from exc
        if not isinstance(payload, dict):
            raise PipelineError("Trend analysis response must be a JSON object")
        return payload

    def _load_prompt_template(self) -> str:
        if self.prompt_template_path.exists():
            text = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if text:
                return text
        return DEFAULT_TREND_PROMPT.strip()

    def _strip_code_fences(self, text: str) -> str:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _extract_json_payload(self, text: str) -> str:
        candidate = self._strip_code_fences(text)
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        decoder = json.JSONDecoder()
        for i, ch in enumerate(candidate):
            if ch != "{":
                continue
            try:
                _, end = decoder.raw_decode(candidate[i:])
            except json.JSONDecodeError:
                continue
            return candidate[i:i + end].strip()
        return candidate.strip()
