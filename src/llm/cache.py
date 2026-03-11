"""Filesystem-backed cache for deterministic LLM outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class CacheRecord:
    """One cached LLM response loaded from disk."""

    key: str
    value: str
    metadata: dict[str, Any]


class FileLLMCache:
    """A tiny JSON file cache keyed by a caller-provided cache key."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the cache directory."""

        self.cache_dir = (cache_dir or Path("data/cache/llm")).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> CacheRecord | None:
        """Return one cached record if the key exists."""

        path = self._path_for_key(key)
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
        return CacheRecord(
            key=str(payload.get("key", key)),
            value=str(payload["value"]),
            metadata=dict(payload.get("metadata", {})),
        )

    def set(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> Path:
        """Persist one cached value and return the written path."""

        path = self._path_for_key(key)
        payload = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def _path_for_key(self, key: str) -> Path:
        """Return the cache file path for one cache key."""

        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"
