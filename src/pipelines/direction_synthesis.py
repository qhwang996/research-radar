"""Pipeline for synthesizing candidate research directions from detected gaps."""

from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.candidate_direction import CandidateDirection
from src.models.enums import DirectionStatus
from src.models.research_gap import ResearchGap
from src.models.theme import Theme
from src.pipelines.base import BasePipeline
from src.repositories.candidate_direction_repository import CandidateDirectionRepository
from src.repositories.research_gap_repository import ResearchGapRepository
from src.repositories.theme_repository import ThemeRepository

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """基于以下研究空白，推荐 2-3 个候选研究方向。

空白：
{{gaps}}

主题：
{{themes}}

请返回 JSON 数组。"""


class DirectionSynthesisPipeline(BasePipeline):
    """Synthesize candidate research directions from detected gaps."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        direction_version: str = "v1",
    ) -> None:
        """Initialize direction synthesis dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/synthesize_from_gaps.md")
        self.direction_version = direction_version

    def process(self, input_data: Any = None) -> list[CandidateDirection]:
        """Synthesize directions from active gaps and persist."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for direction synthesis pipeline")

        session = self.session_factory()
        try:
            gap_repo = ResearchGapRepository(session)
            theme_repo = ThemeRepository(session)

            gaps = gap_repo.list_active()
            if not gaps:
                logger.info("Direction synthesis skipped: no active gaps")
                return []

            themes = theme_repo.list_active_or_core()
            template = self._load_prompt_template()
            prompt = self._build_prompt(template, gaps, themes)

            response_text = self.llm_client.generate(
                prompt,
                model_tier=ModelTier.PREMIUM,
                max_tokens=4000,
                temperature=0.5,
                cache_key=f"direction_{self.direction_version}_{self._current_week_id()}",
            )

            directions_data = self._parse_response(response_text)
            if not directions_data:
                logger.warning("Direction synthesis produced no directions")
                return []

            # Persist
            week_id = self._current_week_id()
            dir_repo = CandidateDirectionRepository(session)
            dir_repo.delete_by_version(self.direction_version)

            saved: list[CandidateDirection] = []
            gap_map = {g.topic.lower().strip(): g for g in gaps}

            for d in directions_data:
                # Link to gap
                gap_topic = (d.get("gap_topic") or "").lower().strip()
                matching_gap = gap_map.get(gap_topic)

                direction = CandidateDirection(
                    title=d.get("title", "Untitled"),
                    description=d.get("description"),
                    rationale=d.get("rationale"),
                    why_now=d.get("why_now"),
                    gap_id=matching_gap.gap_id if matching_gap else None,
                    gap_score=matching_gap.gap_score if matching_gap else None,
                    related_theme_ids=matching_gap.related_theme_ids if matching_gap else [],
                    supporting_artifact_ids=matching_gap.related_artifact_ids if matching_gap else [],
                    key_papers=[],
                    open_questions=d.get("open_questions", []),
                    novelty_score=self._normalize_score(d.get("novelty_score")),
                    impact_score=self._normalize_score(d.get("impact_score")),
                    feasibility_score=self._normalize_score(d.get("feasibility_score")),
                    barrier_score=self._normalize_score(d.get("barrier_score")),
                    composite_direction_score=self._compute_composite(d),
                    status=DirectionStatus.ACTIVE,
                    generation_version=self.direction_version,
                    week_id=week_id,
                )
                saved.append(dir_repo.save(direction))

            logger.info("Direction synthesis complete: %s directions from %s gaps", len(saved), len(gaps))
            return saved
        finally:
            session.close()

    def validate_input(self, data: Any) -> bool:
        return data is None

    def validate_output(self, data: Any) -> bool:
        return isinstance(data, list)

    def _load_prompt_template(self) -> str:
        """Load prompt template from disk or use default."""

        if self.prompt_template_path.exists():
            text = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if text:
                return text
        return DEFAULT_PROMPT_TEMPLATE.strip()

    def _build_prompt(
        self,
        template: str,
        gaps: list[ResearchGap],
        themes: list[Theme],
    ) -> str:
        """Render the synthesis prompt."""

        gaps_text = "\n\n".join(
            f"### 空白: {g.topic} (gap_score={g.gap_score:.2f}, demand={g.demand_frequency})\n"
            f"描述: {g.description or 'N/A'}\n"
            f"学术覆盖: {g.academic_coverage:.0%}"
            for g in gaps[:10]
        )

        themes_text = "\n".join(
            f"- {t.name}: {t.description or 'N/A'} (trend: {t.trend_direction or 'unknown'}, papers: {t.artifact_count})"
            for t in themes[:15]
        )

        prompt = template.replace("{{gaps}}", gaps_text)
        prompt = prompt.replace("{{themes}}", themes_text)
        return prompt

    def _parse_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse the LLM JSON array response."""

        cleaned = self._extract_json_payload(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Direction synthesis response is not valid JSON: {response_text}") from exc

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise PipelineError("Direction synthesis response must be a JSON array")
        return payload

    def _normalize_score(self, raw: Any) -> float | None:
        """Normalize a 1-5 score to 0.0-1.0."""

        if raw is None:
            return None
        try:
            val = float(raw)
            return max(0.0, min(1.0, (val - 1) / 4.0))
        except (TypeError, ValueError):
            return None

    def _compute_composite(self, d: dict[str, Any]) -> float | None:
        """Compute a weighted composite direction score."""

        scores = []
        weights = []
        for key, weight in [("novelty_score", 0.25), ("impact_score", 0.30), ("feasibility_score", 0.20), ("barrier_score", 0.25)]:
            val = self._normalize_score(d.get(key))
            if val is not None:
                scores.append(val * weight)
                weights.append(weight)
        if not weights:
            return None
        return round(sum(scores) / sum(weights), 3)

    def _current_week_id(self) -> str:
        iso_year, iso_week, _ = date.today().isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def _strip_code_fences(self, text: str) -> str:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _extract_json_payload(self, text: str) -> str:
        candidate = self._strip_code_fences(text)
        if (candidate.startswith("[") and candidate.endswith("]")) or \
           (candidate.startswith("{") and candidate.endswith("}")):
            return candidate

        fenced = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", text, flags=re.DOTALL)
        if fenced:
            return fenced.group(1).strip()

        decoder = json.JSONDecoder()
        for i, ch in enumerate(candidate):
            if ch not in "[{":
                continue
            try:
                _, end = decoder.raw_decode(candidate[i:])
            except json.JSONDecodeError:
                continue
            return candidate[i:i + end].strip()

        return candidate.strip()
