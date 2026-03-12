"""LLM-backed enrichment pipeline for artifact summaries and tags."""

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

DEFAULT_PROMPT_TEMPLATE = """You are enriching one security research artifact for a personal research radar.

Return JSON only with this exact schema:
{
  "summary_l1": "one concise sentence",
  "tags": ["tag-one", "tag-two", "tag-three"]
}

Rules:
- summary_l1 must be one sentence and at most 160 characters.
- tags must contain 3 to 5 concise lowercase tags.
- Prefer security-research concepts, attack surfaces, techniques, or systems.
- Do not include markdown fences or extra commentary.

{{artifact_context}}
"""


@dataclass(slots=True)
class EnrichmentPayload:
    """Structured enrichment fields returned from the LLM."""

    summary_l1: str
    tags: list[str]


@dataclass(slots=True, frozen=True)
class ArtifactTask:
    """One artifact selected for enrichment work."""

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


class EnrichmentPipeline(BasePipeline):
    """Generate L1 summaries and keyword tags for persisted artifacts."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        enrich_version: str = "v1",
        max_workers: int = 8,
    ) -> None:
        """Initialize the enrichment pipeline dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/summarize_artifact.md")
        self.enrich_version = enrich_version
        self.max_workers = max(1, max_workers)
        self._thread_local = local()

    def process(self, input_data: Any) -> list[Artifact]:
        """Enrich target artifacts with summary_l1 and tags."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for enrichment pipeline")

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
                if not self._needs_enrichment(artifact):
                    skipped_count += 1
                    continue
                tasks.append(ArtifactTask(order=order, artifact_id=artifact.id, title=artifact.title))
        finally:
            session.close()

        enriched, failed_count = self._run_tasks(tasks, template, profile_context)

        logger.info(
            "Enrichment complete: %s enriched, %s skipped, %s failed",
            len(enriched),
            skipped_count,
            failed_count,
        )

        if not self.validate_output(enriched):
            raise PipelineError("Invalid output from enrichment pipeline")

        return enriched

    def _run_tasks(
        self,
        tasks: list[ArtifactTask],
        template: str,
        profile: ProfileContext | None,
    ) -> tuple[list[Artifact], int]:
        """Run enrichment work in parallel while preserving target order."""

        if not tasks:
            return [], 0

        enriched_by_order: list[tuple[int, Artifact]] = []
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._enrich_one, task.artifact_id, template, profile): task
                for task in tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    artifact = future.result()
                except Exception as exc:  # pragma: no cover - worker boundary
                    failed_count += 1
                    logger.error("Failed to enrich artifact %s (%s): %s", task.artifact_id, task.title, exc)
                    continue
                if artifact is not None:
                    enriched_by_order.append((task.order, artifact))

        enriched_by_order.sort(key=lambda item: item[0])
        return [artifact for _, artifact in enriched_by_order], failed_count

    def _enrich_one(
        self,
        artifact_id: int,
        template: str,
        profile: ProfileContext | None,
    ) -> Artifact | None:
        """Load, enrich, and persist one artifact in one worker thread."""

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            artifact = artifact_repository.get_by_id(artifact_id)
            if artifact is None or not self._needs_enrichment(artifact):
                return None

            prompt = self._build_prompt(template, artifact, profile)
            response_text = self._get_worker_llm_client().generate(
                prompt,
                model_tier=ModelTier.FAST,
                max_tokens=300,
                temperature=0.2,
                cache_key=f"enrichment_{self.enrich_version}_{artifact.canonical_id}",
            )
            payload = self._parse_enrichment_response(response_text)
            artifact.summary_l1 = payload.summary_l1
            artifact.tags = payload.tags
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
        """Return whether the enrichment input is supported."""

        if data is None:
            return True
        if isinstance(data, int):
            return True
        if isinstance(data, Artifact):
            return True
        return isinstance(data, list) and all(isinstance(item, (int, Artifact)) for item in data)

    def validate_output(self, data: Any) -> bool:
        """Return whether the output is a list of artifacts."""

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

    def _needs_enrichment(self, artifact: Artifact) -> bool:
        """Return whether the artifact still lacks Phase 1 enrichment fields."""

        summary_missing = not (artifact.summary_l1 or "").strip()
        tags_missing = len([tag for tag in artifact.tags if str(tag).strip()]) == 0
        return artifact.status == ArtifactStatus.ACTIVE and (summary_missing or tags_missing)

    def _load_prompt_template(self) -> str:
        """Load the prompt template from disk or fall back to the embedded default."""

        if self.prompt_template_path.exists():
            template = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if template:
                return template
        return DEFAULT_PROMPT_TEMPLATE.strip()

    def _build_prompt(self, template: str, artifact: Artifact, profile: Profile | ProfileContext | None) -> str:
        """Render one artifact plus optional profile context into the prompt template."""

        artifact_context = self._build_artifact_context(artifact, profile)
        if "{{artifact_context}}" in template:
            return template.replace("{{artifact_context}}", artifact_context)
        return f"{template}\n\n{artifact_context}"

    def _build_artifact_context(
        self,
        artifact: Artifact,
        profile: Profile | ProfileContext | None,
    ) -> str:
        """Build structured prompt context for one artifact."""

        lines = [
            "Artifact:",
            f"- Title: {artifact.title}",
            f"- Source Type: {artifact.source_type.value}",
            f"- Source Name: {artifact.source_name or 'Unknown'}",
            f"- Source Tier: {artifact.source_tier or 'Unknown'}",
            f"- Year: {artifact.year or 'Unknown'}",
            f"- Authors: {', '.join(artifact.authors) if artifact.authors else 'Unknown'}",
            f"- Abstract: {(artifact.abstract or '').strip() or 'N/A'}",
        ]
        if profile is not None:
            lines.extend(
                [
                    "",
                    "User research context:",
                    f"- Current Area: {profile.current_research_area or 'Unknown'}",
                    f"- Interests: {', '.join(profile.interests) if profile.interests else 'None'}",
                    f"- Preferred Topics: {', '.join(profile.preferred_topics) if profile.preferred_topics else 'None'}",
                    f"- Avoided Topics: {', '.join(profile.avoided_topics) if profile.avoided_topics else 'None'}",
                ]
            )
        return "\n".join(lines)

    def _parse_enrichment_response(self, response_text: str) -> EnrichmentPayload:
        """Parse and normalize one structured LLM response."""

        cleaned = self._strip_code_fences(response_text)
        payload = self._load_payload(cleaned, response_text)

        if not isinstance(payload, dict):
            raise PipelineError("LLM enrichment response must be a JSON object")

        summary = self._normalize_summary(payload.get("summary_l1"))
        tags = self._normalize_tags(payload.get("tags"))
        if not summary:
            raise PipelineError("LLM enrichment response missing summary_l1")
        if not tags:
            raise PipelineError("LLM enrichment response missing tags")

        return EnrichmentPayload(summary_l1=summary, tags=tags)

    def _load_payload(self, cleaned: str, response_text: str) -> dict[str, Any]:
        """Load a structured payload, with a relaxed fallback for common JSON drift."""

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            payload = self._parse_relaxed_payload(cleaned)
            if payload is None:
                raise PipelineError(f"LLM enrichment response is not valid JSON: {response_text}") from None

        if not isinstance(payload, dict):
            raise PipelineError("LLM enrichment response must be a JSON object")
        return payload

    def _parse_relaxed_payload(self, cleaned: str) -> dict[str, Any] | None:
        """Salvage summary/tags from malformed JSON when summary contains bare quotes."""

        summary_match = re.search(r'"summary_l1"\s*:\s*"', cleaned)
        tags_match = re.search(r'"tags"\s*:\s*\[', cleaned)
        if summary_match is None or tags_match is None or summary_match.start() >= tags_match.start():
            return None

        summary_start = summary_match.end()
        summary_end = cleaned.rfind('",', summary_start, tags_match.start())
        if summary_end == -1:
            return None

        tags_start = cleaned.find("[", tags_match.start())
        tags_end = self._find_matching_bracket(cleaned, tags_start)
        if tags_start == -1 or tags_end == -1:
            return None

        try:
            tags = json.loads(cleaned[tags_start : tags_end + 1])
        except json.JSONDecodeError:
            return None

        return {
            "summary_l1": cleaned[summary_start:summary_end],
            "tags": tags,
        }

    def _find_matching_bracket(self, text: str, start_index: int) -> int:
        """Return the matching closing bracket index for one JSON array."""

        if start_index < 0 or start_index >= len(text) or text[start_index] != "[":
            return -1

        depth = 0
        for index in range(start_index, len(text)):
            character = text[index]
            if character == "[":
                depth += 1
            elif character == "]":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    def _strip_code_fences(self, response_text: str) -> str:
        """Remove optional markdown code fences around a JSON payload."""

        candidate = response_text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _normalize_summary(self, value: Any) -> str:
        """Collapse whitespace and return a concise one-line summary."""

        if value is None:
            return ""
        summary = " ".join(str(value).split()).strip()
        if len(summary) > 160:
            summary = summary[:157].rstrip() + "..."
        return summary

    def _normalize_tags(self, value: Any) -> list[str]:
        """Return normalized, deduplicated keyword tags."""

        if not isinstance(value, list):
            return []

        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            tag = str(item).strip().lower()
            tag = re.sub(r"[^a-z0-9\s\-_]", "", tag)
            tag = re.sub(r"\s+", "-", tag)
            tag = re.sub(r"-{2,}", "-", tag).strip("-_")
            if not tag or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
            if len(normalized) >= 5:
                break
        return normalized
