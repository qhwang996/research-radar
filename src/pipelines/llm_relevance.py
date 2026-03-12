"""LLM-backed pipeline for precomputing artifact relevance scores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from threading import local
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import LLMError, PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus
from src.models.profile import Profile
from src.pipelines.base import BasePipeline
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.profile_repository import ProfileRepository

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """你正在为一位安全领域博士研究生评估论文的研究相关度。

用户研究方向：{{research_area}}
核心兴趣：{{interests}}
偏好主题：{{preferred_topics}}
回避主题：{{avoided_topics}}

请评估以下论文与用户研究方向的相关度，打分 1-5：

5 = 直接相关：论文主题是 web 应用安全核心问题（web 漏洞检测与利用、XSS/SQLi/SSRF/CSRF/RCE、Java 反序列化、web 框架安全、服务端安全）
4 = 高度相关：论文方法或场景直接可用于 web 安全（如 web 应用 fuzzing、服务端程序分析、供应链安全、web 相关的漏洞挖掘）
3 = 一般相关：安全领域通用方法，非专门针对 web 场景（如通用 fuzzing 框架、二进制分析、JVM/编译器测试、内核安全、移动安全）
2 = 弱相关：安全领域但与 web 方向较远（如硬件安全、传感器安全、侧信道攻击、网络协议形式化验证、物联网安全）
1 = 不相关：与用户研究方向无关（如纯密码学理论、区块链共识机制、隐私政策用户调研、可用安全问卷研究）

论文信息：
标题：{{title}}
来源：{{source_name}} ({{source_tier}})
摘要：{{summary_l1}}
标签：{{tags}}

请只返回一个 JSON：
{"score": 数字, "reason": "一句话理由"}
"""

RAW_TO_NORMALIZED_SCORE = {
    1: 0.2,
    2: 0.4,
    3: 0.6,
    4: 0.8,
    5: 1.0,
}


@dataclass(slots=True, frozen=True)
class ArtifactTask:
    """One artifact selected for relevance scoring work."""

    order: int
    artifact_id: int
    title: str


@dataclass(slots=True, frozen=True)
class ProfileContext:
    """Detached profile fields needed for prompt rendering."""

    current_research_area: str | None
    interests: tuple[str, ...]
    preferred_topics: tuple[str, ...]
    avoided_topics: tuple[str, ...]


class LLMRelevancePipeline(BasePipeline):
    """Pre-compute LLM relevance scores for artifacts."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        relevance_version: str = "v2",
        max_workers: int = 8,
    ) -> None:
        """Initialize the pipeline dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/relevance_score.md")
        self.relevance_version = relevance_version
        self.max_workers = max(1, max_workers)
        self._thread_local = local()

    def process(self, input_data: Any) -> list[Artifact]:
        """Generate and persist LLM relevance scores for target artifacts."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for LLM relevance pipeline")

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            profile_repository = ProfileRepository(session)
            profile = profile_repository.get_latest_active() or profile_repository.get_latest()
            template = self._load_prompt_template()
            artifacts = self._resolve_targets(artifact_repository, input_data)
            skipped_count = 0
            profile_context = self._snapshot_profile(profile)
            tasks: list[ArtifactTask] = []
            for order, artifact in enumerate(artifacts):
                if not self._needs_llm_relevance(artifact):
                    skipped_count += 1
                    continue
                tasks.append(ArtifactTask(order=order, artifact_id=artifact.id, title=artifact.title))
        finally:
            session.close()

        scored, failed_count = self._run_tasks(tasks, template, profile_context)

        logger.info(
            "LLM relevance complete: %s scored, %s skipped, %s failed",
            len(scored),
            skipped_count,
            failed_count,
        )

        if not self.validate_output(scored):
            raise PipelineError("Invalid output from LLM relevance pipeline")

        return scored

    def _run_tasks(
        self,
        tasks: list[ArtifactTask],
        template: str,
        profile: ProfileContext | None,
    ) -> tuple[list[Artifact], int]:
        """Run relevance scoring work in parallel while preserving target order."""

        if not tasks:
            return [], 0

        scored_by_order: list[tuple[int, Artifact]] = []
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._score_one, task.artifact_id, template, profile): task
                for task in tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    artifact = future.result()
                except Exception as exc:  # pragma: no cover - worker boundary
                    failed_count += 1
                    logger.error(
                        "Failed to compute LLM relevance for artifact %s (%s): %s",
                        task.artifact_id,
                        task.title,
                        exc,
                    )
                    continue
                if artifact is not None:
                    scored_by_order.append((task.order, artifact))

        scored_by_order.sort(key=lambda item: item[0])
        return [artifact for _, artifact in scored_by_order], failed_count

    def _score_one(
        self,
        artifact_id: int,
        template: str,
        profile: ProfileContext | None,
    ) -> Artifact | None:
        """Load, score, and persist one artifact in one worker thread."""

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            artifact = artifact_repository.get_by_id(artifact_id)
            if artifact is None or not self._needs_llm_relevance(artifact):
                return None

            prompt = self._build_prompt(template, artifact, profile)
            response_text = self._get_worker_llm_client().generate(
                prompt,
                model_tier=ModelTier.STANDARD,
                max_tokens=150,
                temperature=0.1,
                cache_key=f"relevance_{self.relevance_version}_{artifact.canonical_id}",
            )
            raw_score = self._parse_score_response(response_text)
            breakdown = dict(artifact.score_breakdown or {})
            breakdown["llm_relevance_score"] = self.map_raw_score(raw_score)
            breakdown["llm_relevance_version"] = self.relevance_version
            artifact.score_breakdown = breakdown
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
            preferred_topics=tuple(profile.preferred_topics or []),
            avoided_topics=tuple(profile.avoided_topics or []),
        )

    def validate_input(self, data: Any) -> bool:
        """Return whether the input selection is supported."""

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

    @classmethod
    def map_raw_score(cls, raw_score: int) -> float:
        """Map a 1-5 LLM score into a normalized 0.0-1.0 score."""

        if raw_score not in RAW_TO_NORMALIZED_SCORE:
            raise ValueError(f"Unsupported LLM relevance score: {raw_score}")
        return RAW_TO_NORMALIZED_SCORE[raw_score]

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

    def _needs_llm_relevance(self, artifact: Artifact) -> bool:
        """Return whether the artifact still needs an LLM relevance score."""

        if artifact.status != ArtifactStatus.ACTIVE:
            return False
        if not artifact.score_breakdown:
            return True
        existing_score = artifact.score_breakdown.get("llm_relevance_score")
        if existing_score is None:
            return True
        existing_version = artifact.score_breakdown.get("llm_relevance_version")
        return existing_version != self.relevance_version

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
            "{{preferred_topics}}": ", ".join(profile.preferred_topics) if profile is not None and profile.preferred_topics else "None",
            "{{avoided_topics}}": ", ".join(profile.avoided_topics) if profile is not None and profile.avoided_topics else "None",
            "{{title}}": artifact.title,
            "{{source_name}}": artifact.source_name or "Unknown",
            "{{source_tier}}": artifact.source_tier or "Unknown",
            "{{summary_l1}}": (artifact.summary_l1 or artifact.abstract or "N/A").strip(),
            "{{tags}}": ", ".join(artifact.tags) if artifact.tags else "None",
        }

        prompt = template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _parse_score_response(self, response_text: str) -> int:
        """Parse one LLM JSON response and return the raw 1-5 score."""

        cleaned = self._strip_code_fences(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"LLM relevance response is not valid JSON: {response_text}") from exc

        if not isinstance(payload, dict):
            raise PipelineError("LLM relevance response must be a JSON object")

        raw_score = payload.get("score")
        try:
            normalized_score = int(raw_score)
        except (TypeError, ValueError) as exc:
            raise PipelineError(f"LLM relevance response has invalid score: {raw_score}") from exc

        if normalized_score not in RAW_TO_NORMALIZED_SCORE:
            raise PipelineError(f"LLM relevance response score must be between 1 and 5: {normalized_score}")
        return normalized_score

    def _strip_code_fences(self, response_text: str) -> str:
        """Remove optional markdown code fences around a JSON payload."""

        candidate = response_text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()
