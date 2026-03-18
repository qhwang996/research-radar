"""LLM-backed pipeline for grouping papers into research themes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import PipelineError
from src.llm import LLMClient, ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType, ThemeStatus
from src.models.profile import Profile
from src.models.theme import Theme
from src.pipelines.base import BasePipeline
from src.repositories.theme_repository import ThemeRepository

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """你是一位安全研究领域的论文聚类专家。

以下是一批安全领域的研究论文摘要。请将它们按研究子领域聚类。

用户研究方向：{{research_area}}

论文列表：
{{paper_list}}

请返回一个 JSON 数组，每个元素表示一个聚类：

[
  {
    "cluster_label": "聚类名称（英文短语，如 Web Application Fuzzing）",
    "description": "这个研究子领域的 2-3 句话描述",
    "paper_ids": [论文ID列表],
    "keywords": ["关键词1", "关键词2", "关键词3"]
  }
]

要求：
- 每个论文必须且只能属于一个聚类
- 聚类名称应反映研究问题，不是泛化描述
- 避免太大的聚类（单个聚类不应超过论文总数的 40%）
- 避免太小的聚类（少于 2 篇的考虑合并到相近聚类）
- 聚类基于研究问题和方法论的相似性，不仅是关键词重叠
- 请只返回 JSON，不要额外解释
"""

MERGE_PROMPT_TEMPLATE = """以下是从多个批次产生的论文聚类标签。请合并语义相似的聚类。

聚类列表：
{{cluster_list}}

请返回合并后的聚类映射 JSON：

[
  {
    "final_label": "合并后的聚类名称",
    "description": "合并后的描述",
    "merged_from": ["原始标签1", "原始标签2"],
    "keywords": ["关键词1", "关键词2"]
  }
]

要求：
- 语义相似的聚类合并为一个
- 不相似的聚类保持独立
- 没有需要合并的就原样返回（merged_from 只包含自身标签）
- 请只返回 JSON，不要额外解释
"""


@dataclass(slots=True, frozen=True)
class ProfileContext:
    """Detached profile fields needed for clustering prompts."""

    current_research_area: str | None


@dataclass(slots=True, frozen=True)
class PaperClusterInput:
    """Compressed artifact representation sent to the clustering prompt."""

    artifact_id: int
    title: str
    year: int | None
    research_problem: str
    methodology: str
    related_concepts: tuple[str, ...]


@dataclass(slots=True)
class BatchCluster:
    """One raw cluster returned from a batch clustering call."""

    cluster_label: str
    description: str
    paper_ids: list[int]
    keywords: list[str]


@dataclass(slots=True)
class MergeCluster:
    """One merged cluster returned from the merge call."""

    final_label: str
    description: str
    merged_from: list[str]
    keywords: list[str]


@dataclass(slots=True)
class ThemeDraft:
    """Intermediate theme payload before persistence."""

    name: str
    description: str
    keywords: list[str]
    artifact_ids: list[int]


class ClusteringPipeline(BasePipeline):
    """Group high-relevance papers into research themes via LLM clustering."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        llm_client: LLMClient | Any | None = None,
        prompt_template_path: Path | None = None,
        cluster_version: str = "v1",
        min_relevance: float = 0.6,
        batch_size: int = 35,
    ) -> None:
        """Initialize clustering dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.llm_client = llm_client or LLMClient()
        self.prompt_template_path = prompt_template_path or Path("prompts/cluster_papers.md")
        self.cluster_version = cluster_version
        self.min_relevance = min_relevance
        self.batch_size = max(1, batch_size)

    def process(self, input_data: Any = None) -> list[Theme]:
        """Run full-paper clustering or a placeholder incremental mode."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for clustering pipeline")

        if input_data == "incremental":
            # TODO: incremental clustering
            logger.warning("Incremental clustering is not implemented yet")
            return []

        session = self.session_factory()
        try:
            profile = self._load_profile(session)
            artifacts = self._load_candidate_artifacts(session)
        finally:
            session.close()

        papers = self._build_cluster_inputs(artifacts)
        if not papers:
            logger.info("Clustering skipped: no eligible papers with summary_l2 available")
            return []

        template = self._load_prompt_template()
        profile_context = self._snapshot_profile(profile)
        batch_clusters = self._cluster_batches(papers, template, profile_context)
        if not batch_clusters:
            logger.warning("Clustering produced no batch clusters")
            return []

        merged_clusters = self._merge_clusters(batch_clusters)
        theme_drafts = self._build_theme_drafts(
            batch_clusters,
            merged_clusters,
            eligible_paper_ids={paper.artifact_id for paper in papers},
        )
        if not theme_drafts:
            logger.warning("Clustering produced no theme drafts")
            return []

        saved = self._persist_themes(theme_drafts, papers)

        logger.info(
            "Clustering complete: %s eligible papers, %s raw clusters, %s themes",
            len(papers),
            len(batch_clusters),
            len(saved),
        )

        if not self.validate_output(saved):
            raise PipelineError("Invalid output from clustering pipeline")

        return saved

    def validate_input(self, data: Any) -> bool:
        """Return whether the pipeline input is supported."""

        return data is None or data == "incremental"

    def validate_output(self, data: Any) -> bool:
        """Return whether the pipeline output is a list of themes."""

        return isinstance(data, list) and all(isinstance(item, Theme) for item in data)

    def _load_profile(self, session: Session) -> Profile | None:
        """Load the most recent active profile snapshot."""

        from src.repositories.profile_repository import ProfileRepository

        profile_repository = ProfileRepository(session)
        return profile_repository.get_latest_active() or profile_repository.get_latest()

    def _load_candidate_artifacts(self, session: Session) -> list[Artifact]:
        """Load active, relevant papers that already have summary_l2."""

        statement = (
            select(Artifact)
            .where(Artifact.status == ArtifactStatus.ACTIVE)
            .where(Artifact.source_type == SourceType.PAPERS)
            .where(Artifact.relevance_score >= self.min_relevance)
            .where(Artifact.summary_l2.is_not(None))
            .where(Artifact.summary_l2 != "")
            .order_by(Artifact.id.asc())
        )
        return list(session.scalars(statement))

    def _snapshot_profile(self, profile: Profile | None) -> ProfileContext | None:
        """Detach profile fields needed for LLM prompts."""

        if profile is None:
            return None
        return ProfileContext(current_research_area=profile.current_research_area)

    def _build_cluster_inputs(self, artifacts: list[Artifact]) -> list[PaperClusterInput]:
        """Convert artifacts plus summary_l2 JSON into clustering inputs."""

        papers: list[PaperClusterInput] = []
        for artifact in artifacts:
            payload = self._load_summary_l2_payload(artifact)
            if payload is None:
                continue
            related_concepts = self._normalize_string_list(payload.get("related_concepts"))
            papers.append(
                PaperClusterInput(
                    artifact_id=artifact.id,
                    title=artifact.title,
                    year=artifact.year,
                    research_problem=self._normalize_text(payload.get("research_problem")),
                    methodology=self._normalize_text(payload.get("methodology")),
                    related_concepts=tuple(related_concepts),
                )
            )
        return papers

    def _load_summary_l2_payload(self, artifact: Artifact) -> dict[str, Any] | None:
        """Parse one artifact summary_l2 payload for clustering use."""

        raw_summary = (artifact.summary_l2 or "").strip()
        if not raw_summary:
            return None
        cleaned = self._extract_json_payload(raw_summary)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Skipping artifact %s due to invalid summary_l2 JSON", artifact.id)
            return None
        if not isinstance(payload, dict):
            logger.warning("Skipping artifact %s because summary_l2 is not a JSON object", artifact.id)
            return None
        return payload

    def _cluster_batches(
        self,
        papers: list[PaperClusterInput],
        template: str,
        profile: ProfileContext | None,
    ) -> list[BatchCluster]:
        """Cluster papers batch by batch via LLM."""

        raw_clusters: list[BatchCluster] = []
        for batch_index, batch in enumerate(self._chunk_papers(papers)):
            prompt = self._build_batch_prompt(template, batch, profile)
            cache_key = f"cluster_batch_{self.cluster_version}_{batch_index}_{self._hash_ids([paper.artifact_id for paper in batch])}"
            response_text = self.llm_client.generate(
                prompt,
                model_tier=ModelTier.STANDARD,
                max_tokens=4000,
                temperature=0.3,
                cache_key=cache_key,
            )
            raw_clusters.extend(self._parse_batch_clusters(response_text, {paper.artifact_id for paper in batch}))
        return raw_clusters

    def _merge_clusters(self, raw_clusters: list[BatchCluster]) -> list[MergeCluster]:
        """Merge semantically similar raw clusters into final themes.

        When there are many batch clusters, first deduplicate by label, then
        send only unique labels to the LLM merge step.
        """

        if not raw_clusters:
            return []

        # Deduplicate: group by normalized label, keep the richest description
        label_groups: dict[str, BatchCluster] = {}
        for cluster in raw_clusters:
            norm_label = cluster.cluster_label.strip().lower()
            existing = label_groups.get(norm_label)
            if existing is None or len(cluster.description or "") > len(existing.description or ""):
                label_groups[norm_label] = cluster

        unique_clusters = list(label_groups.values())
        logger.info("Merge: %s raw clusters deduplicated to %s unique labels", len(raw_clusters), len(unique_clusters))

        # If few enough unique labels, skip LLM merge
        if len(unique_clusters) <= 15:
            return [
                MergeCluster(
                    final_label=c.cluster_label,
                    description=c.description,
                    merged_from=[c.cluster_label],
                    keywords=c.keywords,
                )
                for c in unique_clusters
            ]

        # For large numbers, chunk unique clusters and merge in rounds
        chunk_size = 40
        all_merged: list[MergeCluster] = []
        chunks = [unique_clusters[i:i + chunk_size] for i in range(0, len(unique_clusters), chunk_size)]

        for chunk_idx, chunk in enumerate(chunks):
            prompt = MERGE_PROMPT_TEMPLATE.replace("{{cluster_list}}", self._build_cluster_list(chunk))
            cache_key = f"cluster_merge_{self.cluster_version}_{chunk_idx}_{self._hash_strings([c.cluster_label for c in chunk])}"
            try:
                response_text = self.llm_client.generate(
                    prompt,
                    model_tier=ModelTier.STANDARD,
                    max_tokens=4000,
                    temperature=0.2,
                    cache_key=cache_key,
                )
                all_merged.extend(self._parse_merge_clusters(response_text))
            except Exception as exc:
                logger.warning("Merge chunk %s failed, using raw labels: %s", chunk_idx, exc)
                for c in chunk:
                    all_merged.append(
                        MergeCluster(
                            final_label=c.cluster_label,
                            description=c.description,
                            merged_from=[c.cluster_label],
                            keywords=c.keywords,
                        )
                    )

        return all_merged

    def _build_theme_drafts(
        self,
        raw_clusters: list[BatchCluster],
        merged_clusters: list[MergeCluster],
        *,
        eligible_paper_ids: set[int],
    ) -> list[ThemeDraft]:
        """Build final theme drafts from raw and merged cluster outputs."""

        clusters_by_label: dict[str, list[BatchCluster]] = {}
        for cluster in raw_clusters:
            clusters_by_label.setdefault(cluster.cluster_label, []).append(cluster)

        drafts: list[ThemeDraft] = []
        covered_labels: set[str] = set()

        for merged in merged_clusters:
            source_labels = [label for label in merged.merged_from if label in clusters_by_label]
            if not source_labels and merged.final_label in clusters_by_label:
                source_labels = [merged.final_label]
            if not source_labels:
                logger.warning("Merge cluster %r does not reference any known raw labels", merged.final_label)
                continue
            covered_labels.update(source_labels)
            source_clusters = [cluster for label in source_labels for cluster in clusters_by_label[label]]
            artifact_ids = self._dedupe_ints(
                paper_id
                for cluster in source_clusters
                for paper_id in cluster.paper_ids
            )
            if not artifact_ids:
                continue
            keywords = self._dedupe_strings(
                [*merged.keywords, *(keyword for cluster in source_clusters for keyword in cluster.keywords)]
            )
            description = merged.description or next(
                (cluster.description for cluster in source_clusters if cluster.description),
                "",
            )
            drafts.append(
                ThemeDraft(
                    name=merged.final_label,
                    description=description,
                    keywords=keywords,
                    artifact_ids=artifact_ids,
                )
            )

        for label, label_clusters in clusters_by_label.items():
            if label in covered_labels:
                continue
            artifact_ids = self._dedupe_ints(
                paper_id
                for cluster in label_clusters
                for paper_id in cluster.paper_ids
            )
            if not artifact_ids:
                continue
            drafts.append(
                ThemeDraft(
                    name=label,
                    description=next((cluster.description for cluster in label_clusters if cluster.description), ""),
                    keywords=self._dedupe_strings(
                        keyword for cluster in label_clusters for keyword in cluster.keywords
                    ),
                    artifact_ids=artifact_ids,
                )
            )

        assigned_ids = {artifact_id for draft in drafts for artifact_id in draft.artifact_ids}
        unassigned_ids = sorted(eligible_paper_ids - assigned_ids)
        if unassigned_ids:
            logger.warning("Clustering left %s papers unassigned: %s", len(unassigned_ids), unassigned_ids)

        return drafts

    def _persist_themes(self, drafts: list[ThemeDraft], papers: list[PaperClusterInput]) -> list[Theme]:
        """Replace current-version candidate themes and persist new drafts."""

        year_by_artifact_id = {paper.artifact_id: paper.year for paper in papers}
        week_id = self._current_week_id()

        session = self.session_factory()
        try:
            repository = ThemeRepository(session)
            repository.delete_candidates_by_version(self.cluster_version)
            saved: list[Theme] = []
            for draft in drafts:
                theme = Theme(
                    name=draft.name,
                    description=draft.description or None,
                    keywords=draft.keywords,
                    artifact_ids=draft.artifact_ids,
                    artifact_count=len(draft.artifact_ids),
                    paper_count_by_year=self._compute_year_counts(draft.artifact_ids, year_by_artifact_id),
                    methodology_tags=[],
                    open_questions=[],
                    trend_direction=None,
                    status=ThemeStatus.CANDIDATE,
                    generation_version=self.cluster_version,
                    week_id=week_id,
                )
                saved.append(repository.save(theme))
            return saved
        finally:
            session.close()

    def _load_prompt_template(self) -> str:
        """Load the prompt template from disk or use the embedded default."""

        if self.prompt_template_path.exists():
            template = self.prompt_template_path.read_text(encoding="utf-8").strip()
            if template:
                return template
        return DEFAULT_PROMPT_TEMPLATE.strip()

    def _build_batch_prompt(
        self,
        template: str,
        papers: list[PaperClusterInput],
        profile: ProfileContext | None,
    ) -> str:
        """Render the clustering prompt for one paper batch."""

        prompt = template.replace(
            "{{research_area}}",
            (profile.current_research_area or "Unknown") if profile is not None else "Unknown",
        )
        prompt = prompt.replace("{{paper_list}}", self._build_paper_list(papers))
        return prompt

    def _build_paper_list(self, papers: list[PaperClusterInput]) -> str:
        """Render one batch of papers into prompt-friendly text."""

        blocks: list[str] = []
        for paper in papers:
            concepts = ", ".join(paper.related_concepts) if paper.related_concepts else "N/A"
            blocks.append(
                "\n".join(
                    [
                        f"[ID={paper.artifact_id}] 标题: {paper.title}",
                        f"  研究问题: {paper.research_problem or 'N/A'}",
                        f"  方法: {paper.methodology or 'N/A'}",
                        f"  相关概念: {concepts}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    def _build_cluster_list(self, clusters: list[BatchCluster]) -> str:
        """Render raw clusters into merge-prompt text."""

        lines: list[str] = []
        for cluster in clusters:
            keywords = ", ".join(cluster.keywords) if cluster.keywords else "N/A"
            lines.extend(
                [
                    f"- 标签: {cluster.cluster_label}",
                    f"  描述: {cluster.description or 'N/A'}",
                    f"  关键词: {keywords}",
                    f"  论文ID: {', '.join(str(paper_id) for paper_id in cluster.paper_ids)}",
                ]
            )
        return "\n".join(lines)

    def _parse_batch_clusters(self, response_text: str, valid_ids: set[int]) -> list[BatchCluster]:
        """Parse one batch clustering response."""

        payload = self._load_json_array(response_text, "Batch clustering response")
        clusters: list[BatchCluster] = []
        for item in payload:
            if not isinstance(item, dict):
                logger.warning("Skipping non-object cluster item: %r", item)
                continue
            label = self._normalize_text(item.get("cluster_label"))
            if not label:
                logger.warning("Skipping cluster item without cluster_label")
                continue
            paper_ids = [
                paper_id
                for paper_id in self._normalize_int_list(item.get("paper_ids"))
                if paper_id in valid_ids
            ]
            if not paper_ids:
                logger.warning("Skipping cluster %r because it has no valid paper_ids", label)
                continue
            clusters.append(
                BatchCluster(
                    cluster_label=label,
                    description=self._normalize_text(item.get("description")),
                    paper_ids=self._dedupe_ints(paper_ids),
                    keywords=self._normalize_string_list(item.get("keywords")),
                )
            )
        return clusters

    def _parse_merge_clusters(self, response_text: str) -> list[MergeCluster]:
        """Parse one merge response."""

        payload = self._load_json_array(response_text, "Merge clustering response")
        merged: list[MergeCluster] = []
        for item in payload:
            if not isinstance(item, dict):
                logger.warning("Skipping non-object merge item: %r", item)
                continue
            final_label = self._normalize_text(item.get("final_label"))
            if not final_label:
                logger.warning("Skipping merge item without final_label")
                continue
            merged_from = self._normalize_string_list(item.get("merged_from"))
            if not merged_from:
                merged_from = [final_label]
            merged.append(
                MergeCluster(
                    final_label=final_label,
                    description=self._normalize_text(item.get("description")),
                    merged_from=merged_from,
                    keywords=self._normalize_string_list(item.get("keywords")),
                )
            )
        return merged

    def _load_json_array(self, response_text: str, label: str) -> list[Any]:
        """Extract and parse one JSON array response."""

        cleaned = self._extract_json_payload(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"{label} is not valid JSON: {response_text}") from exc
        if not isinstance(payload, list):
            raise PipelineError(f"{label} must be a JSON array")
        return payload

    def _compute_year_counts(
        self,
        artifact_ids: list[int],
        year_by_artifact_id: dict[int, int | None],
    ) -> dict[str, int]:
        """Count paper years for one theme payload."""

        counts: dict[str, int] = {}
        for artifact_id in artifact_ids:
            year = year_by_artifact_id.get(artifact_id)
            if year is None:
                continue
            key = str(year)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _current_week_id(self) -> str:
        """Return the current ISO week id."""

        iso_year, iso_week, _ = date.today().isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def _chunk_papers(self, papers: list[PaperClusterInput]) -> list[list[PaperClusterInput]]:
        """Split papers into deterministic fixed-size batches."""

        ordered = sorted(papers, key=lambda paper: paper.artifact_id)
        return [
            ordered[index : index + self.batch_size]
            for index in range(0, len(ordered), self.batch_size)
        ]

    def _normalize_text(self, value: Any) -> str:
        """Normalize one text field into a stripped string."""

        if value is None:
            return ""
        return str(value).strip()

    def _normalize_string_list(self, value: Any) -> list[str]:
        """Normalize one list-like field into list[str]."""

        if not isinstance(value, list):
            return []
        return self._dedupe_strings(str(item).strip() for item in value if str(item).strip())

    def _normalize_int_list(self, value: Any) -> list[int]:
        """Normalize one list-like field into list[int]."""

        if not isinstance(value, list):
            return []
        values: list[int] = []
        for item in value:
            try:
                values.append(int(item))
            except (TypeError, ValueError):
                logger.warning("Skipping non-integer paper_id %r in cluster response", item)
        return values

    def _dedupe_ints(self, values: Any) -> list[int]:
        """Deduplicate integers while preserving order."""

        seen: set[int] = set()
        deduped: list[int] = []
        for value in values:
            normalized = int(value)
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _dedupe_strings(self, values: Any) -> list[str]:
        """Deduplicate strings while preserving order."""

        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _hash_ids(self, artifact_ids: list[int]) -> str:
        """Return a stable hash for one artifact id list."""

        return hashlib.sha256(",".join(str(artifact_id) for artifact_id in sorted(artifact_ids)).encode("utf-8")).hexdigest()

    def _hash_strings(self, values: list[str]) -> str:
        """Return a stable hash for one string list."""

        return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()

    def _strip_code_fences(self, response_text: str) -> str:
        """Remove optional markdown code fences around a JSON payload."""

        candidate = response_text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        return candidate.strip()

    def _extract_json_payload(self, response_text: str) -> str:
        """Extract the first JSON array or object from one LLM response."""

        candidate = self._strip_code_fences(response_text)
        if (candidate.startswith("{") and candidate.endswith("}")) or (
            candidate.startswith("[") and candidate.endswith("]")
        ):
            return candidate

        fenced_match = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", response_text, flags=re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        decoder = json.JSONDecoder()
        for index, char in enumerate(candidate):
            if char not in "[{":
                continue
            try:
                _, end = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            return candidate[index : index + end].strip()

        return candidate.strip()
