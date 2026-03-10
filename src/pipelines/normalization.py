"""Normalization pipeline for raw crawler outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
import uuid

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.crawlers.base import clean_text, split_authors
from src.db.session import ENGINE, SessionLocal, create_all_tables
from src.exceptions import PipelineError
from src.models.artifact import Artifact
from src.models.enums import SourceType
from src.repositories.artifact_repository import ArtifactRepository
from src.pipelines.base import BasePipeline

logger = logging.getLogger(__name__)


SOURCE_TIER_BY_NAME = {
    "ndss": "top-tier",
    "ieee s&p": "top-tier",
    "acm ccs": "top-tier",
    "usenix security": "top-tier",
    "portswigger research": "high-quality-blog",
    "google project zero": "high-quality-blog",
    "cloudflare security blog": "high-quality-blog",
}


@dataclass(slots=True)
class RawItemEnvelope:
    """A raw crawler item together with its source payload context."""

    item: dict[str, Any]
    raw_path: Path
    payload: dict[str, Any]
    index: int


class NormalizationPipeline(BasePipeline):
    """Convert raw crawler JSON into persisted Artifact records."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        engine: Engine | None = None,
        normalize_version: str = "v1",
    ) -> None:
        """Initialize the normalization pipeline."""

        self.session_factory = session_factory or SessionLocal
        self.engine = engine or self._extract_engine(self.session_factory) or ENGINE
        self.normalize_version = normalize_version

    def process(self, input_data: Any) -> list[Artifact]:
        """Process raw crawler JSON files and persist normalized artifacts."""

        if not self.validate_input(input_data):
            raise PipelineError("Invalid input for normalization pipeline")

        create_all_tables(self.engine)
        raw_paths = self._resolve_input_paths(input_data)
        envelopes = self._load_envelopes(raw_paths)

        artifacts: list[Artifact] = []
        created_count = 0
        updated_count = 0
        failed_count = 0

        for envelope in envelopes:
            try:
                artifact_fields = self._normalize_envelope(envelope)
                if artifact_fields is None:
                    continue

                session = self.session_factory()
                try:
                    repository = ArtifactRepository(session)
                    artifact, created = self._upsert_artifact(repository, artifact_fields)
                    artifacts.append(artifact)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                finally:
                    session.close()
            except Exception as exc:
                failed_count += 1
                logger.error(
                    "Failed to normalize record %s from %s: %s",
                    envelope.index,
                    envelope.raw_path,
                    exc,
                )

        logger.info(
            "Normalization complete: %s created, %s updated, %s failed from %s raw files",
            created_count,
            updated_count,
            failed_count,
            len(raw_paths),
        )

        if not self.validate_output(artifacts):
            raise PipelineError("Invalid output from normalization pipeline")

        return artifacts

    def validate_input(self, data: Any) -> bool:
        """Return whether the input is a supported path or path collection."""

        try:
            paths = self._resolve_input_paths(data)
        except PipelineError:
            return False
        return len(paths) > 0

    def validate_output(self, data: Any) -> bool:
        """Return whether the output is a list of artifacts."""

        return isinstance(data, list) and all(isinstance(item, Artifact) for item in data)

    def _resolve_input_paths(self, input_data: Any) -> list[Path]:
        """Resolve pipeline input into a sorted list of JSON file paths."""

        if isinstance(input_data, (str, Path)):
            candidates = [Path(input_data)]
        elif isinstance(input_data, list) and all(isinstance(item, (str, Path)) for item in input_data):
            candidates = [Path(item) for item in input_data]
        else:
            raise PipelineError("Normalization input must be a file path, directory path, or list of paths")

        resolved_paths: list[Path] = []
        for candidate in candidates:
            if not candidate.exists():
                raise PipelineError(f"Normalization input does not exist: {candidate}")
            if candidate.is_dir():
                resolved_paths.extend(sorted(candidate.rglob("*.json")))
            elif candidate.suffix == ".json":
                resolved_paths.append(candidate)

        resolved = list(dict.fromkeys(path.resolve() for path in resolved_paths))
        if not resolved:
            raise PipelineError("Normalization input does not contain any JSON files")
        return resolved

    def _load_envelopes(self, raw_paths: list[Path]) -> list[RawItemEnvelope]:
        """Load all supported raw records from the provided file paths."""

        envelopes: list[RawItemEnvelope] = []
        for raw_path in raw_paths:
            try:
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON file %s: %s", raw_path, exc)
                continue

            items = self._extract_items(payload)
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    envelopes.append(
                        RawItemEnvelope(
                            item=item,
                            raw_path=raw_path,
                            payload=payload,
                            index=index,
                        )
                    )

        logger.info("Loaded %s raw records from %s files", len(envelopes), len(raw_paths))
        return envelopes

    def _extract_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract raw items from both legacy and current crawler payload shapes."""

        if isinstance(payload.get("items"), list):
            return payload["items"]
        if isinstance(payload.get("papers"), list):
            return payload["papers"]
        if isinstance(payload.get("articles"), list):
            return payload["articles"]
        return []

    def _normalize_envelope(self, envelope: RawItemEnvelope) -> dict[str, Any] | None:
        """Normalize a raw item into Artifact field values."""

        item = envelope.item
        payload = envelope.payload

        title = clean_text(item.get("title"))
        if not title:
            raise PipelineError(f"Missing title in raw record from {envelope.raw_path}")

        source_type = self._infer_source_type(item, payload, envelope.raw_path)
        content_url = self._extract_content_url(item, payload, envelope.raw_path)
        listing_url = self._extract_listing_url(item, payload)
        published_at = self._parse_datetime(item.get("published_at") or item.get("published_date"))
        fetched_at = self._parse_datetime(payload.get("fetched_at"))
        year = self._infer_year(item, payload, published_at)
        authors = self._normalize_authors(item.get("authors"))
        external_ids = self._build_external_ids(
            item=item,
            payload=payload,
            source_type=source_type,
            content_url=content_url,
            listing_url=listing_url,
        )

        source_name = self._infer_source_name(item, payload)
        canonical_id = self._build_canonical_id(
            title=title,
            source_type=source_type,
            year=year,
            content_url=content_url,
        )

        tags = self._normalize_tags(item.get("tags"))
        abstract = self._extract_abstract(item)
        source_url = content_url or listing_url or envelope.raw_path.resolve().as_uri()

        artifact_fields: dict[str, Any] = {
            "canonical_id": canonical_id,
            "title": title,
            "authors": authors,
            "year": year,
            "source_type": source_type,
            "source_tier": self._infer_source_tier(source_name, source_type),
            "source_name": source_name,
            "source_url": source_url,
            "paper_url": content_url if source_type == SourceType.PAPERS else None,
            "published_at": published_at,
            "fetched_at": fetched_at,
            "abstract": abstract,
            "raw_content_path": str(envelope.raw_path),
            "external_ids": external_ids,
            "tags": tags,
            "normalize_version": self.normalize_version,
        }

        return artifact_fields

    def _upsert_artifact(
        self,
        repository: ArtifactRepository,
        artifact_fields: dict[str, Any],
    ) -> tuple[Artifact, bool]:
        """Create or update an artifact by canonical id."""

        existing = repository.get_by_canonical_id(artifact_fields["canonical_id"])
        if existing is None:
            artifact = Artifact(**artifact_fields)
            return repository.save(artifact), True

        self._merge_artifact(existing, artifact_fields)
        return repository.save(existing), False

    def _merge_artifact(self, artifact: Artifact, new_values: dict[str, Any]) -> None:
        """Merge new normalized fields into an existing artifact."""

        for field, value in new_values.items():
            if field == "canonical_id":
                continue

            if field in {"external_ids", "score_breakdown"}:
                merged = dict(getattr(artifact, field) or {})
                merged.update(value or {})
                setattr(artifact, field, merged)
                continue

            if field in {"tags"}:
                existing_values = list(getattr(artifact, field) or [])
                merged_list = existing_values + [item for item in value or [] if item not in existing_values]
                setattr(artifact, field, merged_list)
                continue

            if field == "authors":
                existing_authors = list(artifact.authors or [])
                candidate_authors = list(value or [])
                if len(candidate_authors) > len(existing_authors):
                    artifact.authors = candidate_authors
                continue

            if field in {"fetched_at", "published_at"}:
                current_value = getattr(artifact, field)
                if current_value is None or (
                    value is not None
                    and self._normalize_datetime_for_compare(value)
                    > self._normalize_datetime_for_compare(current_value)
                ):
                    setattr(artifact, field, value)
                continue

            if value not in (None, "", [], {}):
                setattr(artifact, field, value)

    def _infer_source_type(
        self,
        item: dict[str, Any],
        payload: dict[str, Any],
        raw_path: Path,
    ) -> SourceType:
        """Infer the artifact source type from item, payload, or directory layout."""

        candidates = [
            item.get("source_type"),
            payload.get("source_type"),
            raw_path.parent.name,
        ]
        for candidate in candidates:
            normalized = clean_text(str(candidate)).lower() if candidate else ""
            if normalized in {member.value for member in SourceType}:
                return SourceType(normalized)
        if "article_url" in item or payload.get("total_articles") is not None:
            return SourceType.BLOGS
        return SourceType.PAPERS

    def _infer_source_name(self, item: dict[str, Any], payload: dict[str, Any]) -> str:
        """Infer a human-readable source name for the artifact."""

        source_name = clean_text(payload.get("source"))
        if source_name:
            return source_name
        conference = clean_text(item.get("conference"))
        if conference:
            return conference
        return "Unknown Source"

    def _infer_source_tier(self, source_name: str, source_type: SourceType) -> str:
        """Infer a coarse source tier for downstream scoring."""

        source_key = source_name.lower()
        for candidate, tier in SOURCE_TIER_BY_NAME.items():
            if candidate in source_key:
                return tier
        if source_type == SourceType.PAPERS:
            return "paper"
        if source_type == SourceType.BLOGS:
            return "blog"
        return "unknown"

    def _extract_content_url(
        self,
        item: dict[str, Any],
        payload: dict[str, Any],
        raw_path: Path,
    ) -> str | None:
        """Extract the URL that points to the individual content item."""

        candidates = [
            item.get("paper_url"),
            item.get("article_url"),
            item.get("pdf_url"),
            item.get("source_url"),
            item.get("url"),
            payload.get("url"),
            payload.get("source_url"),
        ]
        for candidate in candidates:
            cleaned = clean_text(candidate)
            if cleaned:
                return cleaned
        return raw_path.resolve().as_uri()

    def _extract_listing_url(self, item: dict[str, Any], payload: dict[str, Any]) -> str | None:
        """Extract the listing page URL if it differs from the content URL."""

        candidates = [
            item.get("source_url"),
            payload.get("url"),
            payload.get("source_url"),
        ]
        for candidate in candidates:
            cleaned = clean_text(candidate)
            if cleaned:
                return cleaned
        return None

    def _infer_year(
        self,
        item: dict[str, Any],
        payload: dict[str, Any],
        published_at: datetime | None,
    ) -> int | None:
        """Infer the year for a raw item."""

        direct_year = item.get("year")
        if isinstance(direct_year, int):
            return direct_year
        if isinstance(direct_year, str) and direct_year.isdigit():
            return int(direct_year)

        conference = clean_text(item.get("conference"))
        match = re.search(r"(20\d{2})", conference)
        if match:
            return int(match.group(1))

        if published_at:
            return published_at.year

        payload_year = payload.get("year")
        if isinstance(payload_year, int):
            return payload_year
        return None

    def _normalize_authors(self, raw_authors: Any) -> list[str]:
        """Normalize raw author values into a cleaned string list."""

        if isinstance(raw_authors, list):
            authors = [clean_text(str(author)) for author in raw_authors if clean_text(str(author))]
        elif isinstance(raw_authors, str):
            authors = split_authors(raw_authors)
        else:
            authors = []

        deduped: list[str] = []
        for author in authors:
            if author not in deduped:
                deduped.append(author)
        return deduped

    def _normalize_tags(self, raw_tags: Any) -> list[str]:
        """Normalize raw tags into a clean, unique list."""

        if not raw_tags:
            return []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        if not isinstance(raw_tags, list):
            return []

        tags: list[str] = []
        for tag in raw_tags:
            cleaned = clean_text(str(tag))
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
        return tags

    def _extract_abstract(self, item: dict[str, Any]) -> str | None:
        """Return the best available text summary from the raw item."""

        for key in ["abstract", "excerpt", "summary"]:
            value = clean_text(item.get(key))
            if value:
                return value
        return None

    def _build_external_ids(
        self,
        *,
        item: dict[str, Any],
        payload: dict[str, Any],
        source_type: SourceType,
        content_url: str | None,
        listing_url: str | None,
    ) -> dict[str, str]:
        """Build auxiliary external identifiers for the artifact."""

        external_ids: dict[str, str] = {}
        if listing_url:
            external_ids["listing_url"] = listing_url
        if content_url:
            external_ids["content_url"] = content_url

        for field in ["conference", "cycle", "source_slug"]:
            value = clean_text(item.get(field) or payload.get(field))
            if value:
                external_ids[field] = value

        source_name = clean_text(payload.get("source"))
        if source_name:
            external_ids["raw_source"] = source_name

        if content_url:
            parsed = urlparse(content_url)
            if parsed.netloc:
                external_ids["host"] = parsed.netloc.lower()
            doi_match = re.search(r"10\.\d{4,9}/\S+", content_url)
            if doi_match:
                external_ids["doi"] = doi_match.group(0).rstrip(")")

        if source_type == SourceType.BLOGS and item.get("article_url"):
            external_ids["article_url"] = clean_text(item.get("article_url"))

        return external_ids

    def _build_canonical_id(
        self,
        *,
        title: str,
        source_type: SourceType,
        year: int | None,
        content_url: str | None,
    ) -> str:
        """Build a stable UUID5 canonical id for a normalized record."""

        title_key = self._normalize_title_key(title)
        if source_type == SourceType.BLOGS:
            host = urlparse(content_url).netloc.lower() if content_url else "unknown-host"
            fingerprint = f"{source_type.value}|{host}|{title_key}"
        else:
            fingerprint = f"{source_type.value}|{year or 'unknown-year'}|{title_key}"

        return str(uuid.uuid5(uuid.NAMESPACE_URL, fingerprint))

    def _normalize_title_key(self, title: str) -> str:
        """Normalize a title into a deduplication key."""

        normalized = clean_text(title).lower()
        normalized = re.sub(r"[\"'“”‘’`´]", "", normalized)
        normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
        return normalized.strip("-")

    def _parse_datetime(self, raw_value: Any) -> datetime | None:
        """Parse ISO-like datetime strings into datetime objects."""

        if not raw_value:
            return None
        if isinstance(raw_value, datetime):
            return raw_value

        candidate = clean_text(str(raw_value))
        if not candidate:
            return None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            candidate = f"{candidate}T00:00:00"
        candidate = candidate.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    def _normalize_datetime_for_compare(self, value: datetime) -> datetime:
        """Normalize naive and aware datetimes into UTC-aware values for comparison."""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _extract_engine(self, factory: sessionmaker[Session]) -> Engine | None:
        """Extract the bound engine from a session factory if available."""

        bind = getattr(factory, "kw", {}).get("bind")
        if isinstance(bind, Engine):
            return bind
        return None
