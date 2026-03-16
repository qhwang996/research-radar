"""LLM-backed pipeline for extracting demand signals from blog posts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from threading import local
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.pipelines.base import BasePipeline
from src.repositories.artifact_repository import ArtifactRepository

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """你是一位安全研究分析专家。请从以下行业安全博客文章中提取需求信号。

需求信号指的是：工业界正在面对什么安全问题、现有解决方案有什么不足、为什么这个问题现在变得重要。

文章信息：
标题：{{title}}
来源：{{source_name}}
摘要/内容：{{content}}
标签：{{tags}}

请返回一个 JSON，不要加 Markdown 代码块，不要额外解释：

{
  "signal_type": "demand",
  "problem_described": "文章描述的核心安全问题（1-2 句话）",
  "affected_systems": ["受影响的系统或技术1", "系统2"],
  "current_solutions": "文章提到的现有解决方案（如果有，1-2 句话；没有就写'未提及'）",
  "solution_gaps": ["现有方案的不足或缺口1", "缺口2"],
  "urgency_indicators": ["为什么这个问题现在重要1", "原因2"],
  "related_academic_topics": ["相关的学术研究主题1", "主题2", "主题3"]
}

要求：
- problem_described 必须具体，不要泛泛而谈
- solution_gaps 对后续空白检测最重要，尽量具体指出现有方案做不到什么
- related_academic_topics 列出 3-5 个，使用学术领域的规范术语（如 fuzzing、program analysis、vulnerability detection）
- affected_systems 列出 1-3 个
- 如果文章信息有限，基于标题做合理推断，在 solution_gaps 中注明信息不足
- 使用中文
"""


@dataclass(slots=True, frozen=True)
class SignalTask:
    """One blog artifact selected for signal extraction."""

    order: int
    artifact_id: int
    title: str


class SignalExtractionPipeline(BasePipeline):
    """Extract structured demand signals from industry blog posts."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        signal_version: str = "v1",
        min_relevance: float = 0.3,
        max_workers: int = 4,
    ) -> None:
        """Initialize the signal extraction pipeline."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/extract_demand_signal.md")
        self.signal_version = signal_version
        self.min_relevance = min_relevance
        self.max_workers = max(1, max_workers)
        self._thread_local = local()

    def process(self, input_data: Any = None) -> list[Artifact]:
        """Extract and persist demand signals for blog artifacts."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for signal extraction pipeline")

        session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            if isinstance(input_data, int):
                artifact = repository.get_by_id(input_data)
                artifacts = [artifact] if artifact else []
            else:
                artifacts = self._load_candidate_blogs(session)
            template = self._load_prompt_template()
            tasks: list[SignalTask] = []
            skipped = 0
            for order, artifact in enumerate(artifacts):
                if not self._needs_signal_extraction(artifact):
                    skipped += 1
                    continue
                tasks.append(SignalTask(order=order, artifact_id=artifact.id, title=artifact.title))
        finally:
            session.close()

        extracted, failed = self._run_tasks(tasks, template)

        logger.info(
            "Signal extraction complete: %s extracted, %s skipped, %s failed",
            len(extracted),
            skipped,
            failed,
        )

        if not self.validate_output(extracted):
            raise PipelineError("Invalid output from signal extraction pipeline")

        return extracted

    def validate_input(self, data: Any) -> bool:
        """Return whether the input is supported."""

        return data is None or isinstance(data, int)

    def validate_output(self, data: Any) -> bool:
        """Return whether the output is a list of artifacts."""

        return isinstance(data, list) and all(isinstance(item, Artifact) for item in data)

    def _load_candidate_blogs(self, session: Session) -> list[Artifact]:
        """Load blog artifacts eligible for signal extraction."""

        statement = (
            select(Artifact)
            .where(Artifact.status == ArtifactStatus.ACTIVE)
            .where(Artifact.source_type == SourceType.BLOGS)
            .where(Artifact.summary_l2.is_(None) | (Artifact.summary_l2 == ""))
            .order_by(Artifact.id.asc())
        )
        # Apply relevance filter only if scores exist
        candidates = list(session.scalars(statement))
        return [
            a for a in candidates
            if a.relevance_score is None or a.relevance_score >= self.min_relevance
        ]

    def _needs_signal_extraction(self, artifact: Artifact) -> bool:
        """Check if the artifact needs signal extraction."""

        if artifact.status != ArtifactStatus.ACTIVE:
            return False
        if artifact.source_type != SourceType.BLOGS:
            return False
        existing = (artifact.summary_l2 or "").strip()
        if not existing:
            return True
        # Check if already has demand signal
        try:
            payload = json.loads(existing)
            return payload.get("signal_type") != "demand"
        except (json.JSONDecodeError, AttributeError):
            return True

    def _run_tasks(
        self,
        tasks: list[SignalTask],
        template: str,
    ) -> tuple[list[Artifact], int]:
        """Run signal extraction in parallel."""

        if not tasks:
            return [], 0

        results: list[tuple[int, Artifact]] = []
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._extract_one, task.artifact_id, template): task
                for task in tasks
            }
            for future in as_completed(future_map):
                task = future_map[future]
                try:
                    artifact = future.result()
                except Exception as exc:
                    failed += 1
                    logger.error(
                        "Failed signal extraction for artifact %s (%s): %s",
                        task.artifact_id, task.title, exc,
                    )
                    continue
                if artifact is not None:
                    results.append((task.order, artifact))

        results.sort(key=lambda x: x[0])
        return [a for _, a in results], failed

    def _extract_one(self, artifact_id: int, template: str) -> Artifact | None:
        """Extract demand signal for one blog artifact."""

        session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            artifact = repository.get_by_id(artifact_id)
            if artifact is None or not self._needs_signal_extraction(artifact):
                return None

            prompt = self._build_prompt(template, artifact)
            response_text = self._get_worker_llm_client().generate(
                prompt,
                model_tier=ModelTier.STANDARD,
                max_tokens=1000,
                temperature=0.3,
                cache_key=f"signal_{self.signal_version}_{artifact.canonical_id}",
            )

            payload = self._parse_signal_response(response_text)
            artifact.summary_l2 = json.dumps(payload, ensure_ascii=False)
            return repository.save(artifact)
        finally:
            session.close()

    def _get_worker_llm_client(self) -> LLMClient | Any:
        """Return a thread-local LLM client."""

        if not isinstance(self.llm_client, LLMClient):
            return self.llm_client

        client = getattr(self._thread_local, "llm_client", None)
        if client is None:
            client = LLMClient(
                provider=self.llm_client.provider.provider_name,
                cache_dir=self.llm_client.cache.cache_dir,
                timeout=self.llm_client.timeout,
                max_retries=self.llm_client.max_retries,
                backoff_base_seconds=self.llm_client.backoff_base_seconds,
                sleep_fn=self.llm_client.sleep_fn,
                model_map=dict(self.llm_client.model_map),
            )
            self._thread_local.llm_client = client
        return client

    def _load_prompt_template(self) -> str:
        """Load prompt template from disk or use default."""

        if self.prompt_template_path.exists():
            text = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if text:
                return text
        return DEFAULT_PROMPT_TEMPLATE.strip()

    def _build_prompt(self, template: str, artifact: Artifact) -> str:
        """Render the prompt for one blog artifact."""

        content = artifact.abstract or artifact.summary_l1 or "N/A"
        replacements = {
            "{{title}}": artifact.title,
            "{{source_name}}": artifact.source_name or "Unknown",
            "{{content}}": content.strip(),
            "{{tags}}": ", ".join(artifact.tags) if artifact.tags else "None",
        }
        prompt = template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _parse_signal_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM response into a demand signal dict."""

        cleaned = self._extract_json_payload(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Signal extraction response is not valid JSON: {response_text}") from exc

        if not isinstance(payload, dict):
            raise PipelineError("Signal extraction response must be a JSON object")

        # Ensure signal_type is present
        payload.setdefault("signal_type", "demand")
        return payload

    def _strip_code_fences(self, text: str) -> str:
        """Remove optional markdown code fences."""

        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _extract_json_payload(self, text: str) -> str:
        """Extract the first JSON object from an LLM response."""

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
