"""LLM-backed enrichment pipeline for artifact summaries and tags."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
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


class EnrichmentPipeline(BasePipeline):
    """Generate L1 summaries and keyword tags for persisted artifacts."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        enrich_version: str = "v1",
    ) -> None:
        """Initialize the enrichment pipeline dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/summarize_artifact.md")
        self.enrich_version = enrich_version

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

            enriched: list[Artifact] = []
            failed_count = 0
            skipped_count = 0

            for artifact in artifacts:
                if not self._needs_enrichment(artifact):
                    skipped_count += 1
                    continue

                try:
                    prompt = self._build_prompt(template, artifact, profile)
                    response_text = self.llm_client.generate(
                        prompt,
                        model_tier=ModelTier.FAST,
                        max_tokens=300,
                        temperature=0.2,
                        cache_key=f"enrichment_{self.enrich_version}_{artifact.canonical_id}",
                    )
                    payload = self._parse_enrichment_response(response_text)
                    artifact.summary_l1 = payload.summary_l1
                    artifact.tags = payload.tags
                    enriched.append(artifact_repository.save(artifact))
                except (LLMError, PipelineError, ValueError, TypeError) as exc:
                    failed_count += 1
                    logger.error("Failed to enrich artifact %s (%s): %s", artifact.id, artifact.title, exc)

            logger.info(
                "Enrichment complete: %s enriched, %s skipped, %s failed",
                len(enriched),
                skipped_count,
                failed_count,
            )

            if not self.validate_output(enriched):
                raise PipelineError("Invalid output from enrichment pipeline")

            return enriched
        finally:
            session.close()

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

    def _build_prompt(self, template: str, artifact: Artifact, profile: Profile | None) -> str:
        """Render one artifact plus optional profile context into the prompt template."""

        artifact_context = self._build_artifact_context(artifact, profile)
        if "{{artifact_context}}" in template:
            return template.replace("{{artifact_context}}", artifact_context)
        return f"{template}\n\n{artifact_context}"

    def _build_artifact_context(self, artifact: Artifact, profile: Profile | None) -> str:
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
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"LLM enrichment response is not valid JSON: {response_text}") from exc

        if not isinstance(payload, dict):
            raise PipelineError("LLM enrichment response must be a JSON object")

        summary = self._normalize_summary(payload.get("summary_l1"))
        tags = self._normalize_tags(payload.get("tags"))
        if not summary:
            raise PipelineError("LLM enrichment response missing summary_l1")
        if not tags:
            raise PipelineError("LLM enrichment response missing tags")

        return EnrichmentPayload(summary_l1=summary, tags=tags)

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
