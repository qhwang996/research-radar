"""LLM-backed pipeline for structured L2 paper analysis."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
from threading import local
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.models.profile import Profile
from src.pipelines.base import BasePipeline
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.profile_repository import ProfileRepository

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """你是一位安全研究领域的论文分析专家。请对以下论文进行结构化深度分析。

用户研究方向：{{research_area}}
核心兴趣：{{interests}}

论文信息：
标题：{{title}}
来源：{{source_name}} ({{source_tier}})，{{year}} 年
作者：{{authors}}
摘要：{{abstract}}
一句话总结：{{summary_l1}}
标签：{{tags}}

请返回一个 JSON，不要加 Markdown 代码块，不要额外解释：

{
  "research_problem": "这篇论文要解决的核心问题（1-2 句话）",
  "motivation": "为什么这个问题重要，现有方案有什么不足（1-2 句话）",
  "methodology": "核心方法或技术路线（1-2 句话）",
  "core_contributions": ["主要贡献1", "主要贡献2"],
  "limitations": ["局限性1", "局限性2"],
  "open_questions": ["论文提出或暗示的待解决问题1", "问题2"],
  "related_concepts": ["相关的核心概念或技术1", "技术2"]
}

要求：
- 每个字段必须有实质内容，不要泛泛而谈
- limitations 和 open_questions 对后续研究选题最重要，请尽量具体
- core_contributions 列出 2-3 个，limitations 列出 1-3 个，open_questions 列出 1-3 个
- related_concepts 列出 3-5 个核心概念/技术，用于后续主题聚类
- 如果论文摘要信息有限，基于标题和来源做合理推断，但在 limitations 中注明信息不足
- 使用中文
"""

@dataclass(slots=True)
class DeepAnalysisPayload:
    """Structured L2 analysis returned from the LLM."""

    research_problem: str
    motivation: str
    methodology: str
    core_contributions: list[str]
    limitations: list[str]
    open_questions: list[str]
    related_concepts: list[str]


@dataclass(slots=True, frozen=True)
class ArtifactTask:
    """One artifact selected for deep analysis work."""

    order: int
    artifact_id: int
    title: str
    force_relevance: bool = False


@dataclass(slots=True, frozen=True)
class ProfileContext:
    """Detached profile fields needed for prompt rendering."""

    current_research_area: str | None
    interests: tuple[str, ...]


class DeepAnalysisPipeline(BasePipeline):
    """Generate structured L2 deep analysis for high-relevance papers."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        analysis_version: str = "v1",
        min_relevance: float = 0.6,
        max_workers: int = 4,
    ) -> None:
        """Initialize the deep-analysis pipeline dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/deep_analysis.md")
        self.analysis_version = analysis_version
        self.min_relevance = min_relevance
        self.max_workers = max(1, max_workers)
        self._thread_local = local()

    def process(self, input_data: Any) -> list[Artifact]:
        """Generate and persist deep analysis payloads for target artifacts."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for deep analysis pipeline")

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            profile_repository = ProfileRepository(session)
            profile = profile_repository.get_latest_active() or profile_repository.get_latest()
            template = self._load_prompt_template()
            artifacts = self._resolve_targets(artifact_repository, input_data)
            forced_ids = self._forced_relevance_ids(input_data)
            skipped_count = 0
            profile_context = self._snapshot_profile(profile)
            tasks: list[ArtifactTask] = []
            for order, artifact in enumerate(artifacts):
                force_relevance = artifact.id in forced_ids
                if not self._needs_analysis(artifact, force_relevance=force_relevance):
                    skipped_count += 1
                    continue
                tasks.append(
                    ArtifactTask(
                        order=order,
                        artifact_id=artifact.id,
                        title=artifact.title,
                        force_relevance=force_relevance,
                    )
                )
        finally:
            session.close()

        analyzed, failed_count = self._run_tasks(tasks, template, profile_context)

        logger.info(
            "Deep analysis complete: %s analyzed, %s skipped, %s failed",
            len(analyzed),
            skipped_count,
            failed_count,
        )

        if not self.validate_output(analyzed):
            raise PipelineError("Invalid output from deep analysis pipeline")

        return analyzed

    def _run_tasks(
        self,
        tasks: list[ArtifactTask],
        template: str,
        profile: ProfileContext | None,
    ) -> tuple[list[Artifact], int]:
        """Run deep analysis work in parallel while preserving target order."""

        if not tasks:
            return [], 0

        analyzed_by_order: list[tuple[int, Artifact]] = []
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._analyze_one, task.artifact_id, template, profile, task.force_relevance): task
                for task in tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    artifact = future.result()
                except Exception as exc:  # pragma: no cover - worker boundary
                    failed_count += 1
                    logger.error(
                        "Failed to generate deep analysis for artifact %s (%s): %s",
                        task.artifact_id,
                        task.title,
                        exc,
                    )
                    continue
                if artifact is not None:
                    analyzed_by_order.append((task.order, artifact))

        analyzed_by_order.sort(key=lambda item: item[0])
        return [artifact for _, artifact in analyzed_by_order], failed_count

    def _analyze_one(
        self,
        artifact_id: int,
        template: str,
        profile: ProfileContext | None,
        force_relevance: bool,
    ) -> Artifact | None:
        """Load, analyze, and persist one artifact in one worker thread."""

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            artifact = artifact_repository.get_by_id(artifact_id)
            if artifact is None or not self._needs_analysis(artifact, force_relevance=force_relevance):
                return None

            prompt = self._build_prompt(template, artifact, profile)
            response_text = self._get_worker_llm_client().generate(
                prompt,
                model_tier=ModelTier.STANDARD,
                max_tokens=1500,
                temperature=0.3,
                cache_key=f"deep_analysis_{self.analysis_version}_{artifact.canonical_id}",
            )
            payload = self._parse_analysis_response(response_text)
            artifact.summary_l2 = json.dumps(asdict(payload), ensure_ascii=False)
            return artifact_repository.save(artifact)
        finally:
            session.close()

    def _get_worker_llm_client(self) -> LLMClient | Any:
        """Return one thread-local client for real LLM calls and reuse stubs in tests."""

        if not isinstance(self.llm_client, LLMClient):
            return self.llm_client

        worker_client = getattr(self._thread_local, "llm_client", None)
        if worker_client is None:
            worker_client = LLMClient(
                provider=self.llm_client.provider.provider_name,
                cache_dir=self.llm_client.cache.cache_dir,
                timeout=self.llm_client.timeout,
                max_retries=self.llm_client.max_retries,
                backoff_base_seconds=self.llm_client.backoff_base_seconds,
                sleep_fn=self.llm_client.sleep_fn,
                model_map=dict(self.llm_client.model_map),
            )
            self._thread_local.llm_client = worker_client
        return worker_client

    def _snapshot_profile(self, profile: Profile | None) -> ProfileContext | None:
        """Detach the prompt-relevant profile fields for worker-thread use."""

        if profile is None:
            return None
        return ProfileContext(
            current_research_area=profile.current_research_area,
            interests=tuple(profile.interests or []),
        )

    def validate_input(self, data: Any) -> bool:
        """Return whether the deep-analysis input selection is supported."""

        if data is None:
            return True
        if isinstance(data, int):
            return True
        if isinstance(data, Artifact):
            return True
        return isinstance(data, list) and all(isinstance(item, (int, Artifact)) for item in data)

    def validate_output(self, data: Any) -> bool:
        """Return whether the pipeline output is a list of artifacts."""

        return isinstance(data, list) and all(isinstance(item, Artifact) for item in data)

    def _resolve_targets(self, repository: ArtifactRepository, input_data: Any) -> list[Artifact]:
        """Resolve pipeline input into a deterministic artifact list."""

        if input_data is None:
            return repository.list_by_status(ArtifactStatus.ACTIVE)

        if isinstance(input_data, Artifact):
            return [input_data]

        if isinstance(input_data, int):
            artifact = repository.get_by_id(input_data)
            return [artifact] if artifact is not None else []

        resolved: list[Artifact] = []
        for item in input_data:
            if isinstance(item, Artifact):
                resolved.append(item)
                continue
            artifact = repository.get_by_id(item)
            if artifact is not None:
                resolved.append(artifact)
        return resolved

    def _forced_relevance_ids(self, input_data: Any) -> set[int]:
        """Return directly targeted ids that should bypass the relevance threshold."""

        if isinstance(input_data, int):
            return {input_data}
        if not isinstance(input_data, list):
            return set()
        return {item for item in input_data if isinstance(item, int)}

    def _needs_analysis(self, artifact: Artifact, *, force_relevance: bool = False) -> bool:
        """Return whether the artifact still needs deep analysis."""

        if artifact.status != ArtifactStatus.ACTIVE:
            return False
        if artifact.source_type != SourceType.PAPERS:
            return False
        if (artifact.summary_l2 or "").strip():
            return False
        if force_relevance:
            return True
        return artifact.relevance_score is not None and artifact.relevance_score >= self.min_relevance

    def _load_prompt_template(self) -> str:
        """Load the prompt template from disk or use the embedded default."""

        if self.prompt_template_path.exists():
            template = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if template:
                return template
        return DEFAULT_PROMPT_TEMPLATE.strip()

    def _build_prompt(self, template: str, artifact: Artifact, profile: Profile | ProfileContext | None) -> str:
        """Render prompt placeholders for one artifact/profile pair."""

        replacements = {
            "{{research_area}}": (profile.current_research_area or "Unknown") if profile is not None else "Unknown",
            "{{interests}}": ", ".join(profile.interests) if profile is not None and profile.interests else "None",
            "{{title}}": artifact.title,
            "{{source_name}}": artifact.source_name or "Unknown",
            "{{source_tier}}": artifact.source_tier or "Unknown",
            "{{year}}": str(artifact.year or "Unknown"),
            "{{authors}}": ", ".join(artifact.authors) if artifact.authors else "N/A",
            "{{abstract}}": (artifact.abstract or "N/A").strip() or "N/A",
            "{{summary_l1}}": (artifact.summary_l1 or "N/A").strip() or "N/A",
            "{{tags}}": ", ".join(str(tag).strip() for tag in artifact.tags if str(tag).strip()) or "N/A",
        }

        prompt = template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _parse_analysis_response(self, response_text: str) -> DeepAnalysisPayload:
        """Parse and normalize one structured deep-analysis response."""

        cleaned = self._extract_json_payload(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Deep analysis response is not valid JSON: {response_text}") from exc

        if not isinstance(payload, dict):
            raise PipelineError("Deep analysis response must be a JSON object")

        normalized = {
            "research_problem": self._normalize_text_field(payload, "research_problem"),
            "motivation": self._normalize_text_field(payload, "motivation"),
            "methodology": self._normalize_text_field(payload, "methodology"),
            "core_contributions": self._normalize_string_list(payload, "core_contributions"),
            "limitations": self._normalize_string_list(payload, "limitations"),
            "open_questions": self._normalize_string_list(payload, "open_questions"),
            "related_concepts": self._normalize_string_list(payload, "related_concepts"),
        }
        return DeepAnalysisPayload(**normalized)

    def _normalize_text_field(self, payload: dict[str, Any], key: str) -> str:
        """Return a cleaned string field, degrading missing values to empty strings."""

        value = payload.get(key)
        if value is None:
            logger.warning("Deep analysis response missing %s; degrading to empty string", key)
            return ""
        if isinstance(value, str):
            cleaned = value.strip()
        else:
            logger.warning("Deep analysis response has non-string %s=%r; coercing to string", key, value)
            cleaned = str(value).strip()
        if not cleaned:
            logger.warning("Deep analysis response has empty %s after normalization", key)
        return cleaned

    def _normalize_string_list(self, payload: dict[str, Any], key: str) -> list[str]:
        """Return a cleaned list[str] field, degrading missing values to empty lists."""

        value = payload.get(key)
        if value is None:
            logger.warning("Deep analysis response missing %s; degrading to empty list", key)
            return []
        if not isinstance(value, list):
            logger.warning("Deep analysis response has non-list %s=%r; degrading to empty list", key, value)
            return []

        items: list[str] = []
        for item in value:
            if item is None:
                continue
            if not isinstance(item, str):
                logger.warning("Deep analysis response has non-string item in %s=%r; coercing to string", key, item)
            normalized = str(item).strip()
            if normalized:
                items.append(normalized)
        if not items:
            logger.warning("Deep analysis response has empty %s after normalization", key)
        return items

    def _strip_code_fences(self, response_text: str) -> str:
        """Remove optional markdown code fences around a JSON payload."""

        candidate = response_text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _extract_json_payload(self, response_text: str) -> str:
        """Extract the first JSON object from one LLM response."""

        candidate = self._strip_code_fences(response_text)
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate

        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, flags=re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        decoder = json.JSONDecoder()
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                _, end = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            return candidate[index : index + end].strip()

        return candidate.strip()
