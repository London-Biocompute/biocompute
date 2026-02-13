"""Local file-based cache for experiment submissions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_CACHE_DIR = Path.home() / ".lbc" / "cache"


def cache_key(challenge_id: str, experiments: list[list[dict[str, Any]]]) -> str:
    """Compute a deterministic SHA-256 key from challenge_id + experiments payload."""
    payload = json.dumps(
        {"challenge_id": challenge_id, "experiments": experiments},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class CacheEntry:
    """A cached submission record."""

    challenge_id: str
    experiments_hash: str
    job_id: str
    status: str
    result: dict[str, Any] | list[Any] | None = None
    error: str | None = None


def get(key: str, *, cache_dir: Path | None = None) -> CacheEntry | None:
    """Load a cache entry by key, or None if not found."""
    d = cache_dir if cache_dir is not None else _CACHE_DIR
    p = d / f"{key}.json"
    if not p.exists():
        return None
    data: dict[str, Any] = json.loads(p.read_text())
    return CacheEntry(**data)


def put(key: str, entry: CacheEntry, *, cache_dir: Path | None = None) -> None:
    """Write a cache entry to disk."""
    d = cache_dir if cache_dir is not None else _CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{key}.json"
    p.write_text(json.dumps(asdict(entry), sort_keys=True, indent=2) + "\n")


def remove(key: str, *, cache_dir: Path | None = None) -> None:
    """Remove a cache entry if it exists."""
    d = cache_dir if cache_dir is not None else _CACHE_DIR
    p = d / f"{key}.json"
    if p.exists():
        p.unlink()


def clear(*, cache_dir: Path | None = None) -> int:
    """Remove all cache entries. Returns the number of entries removed."""
    d = cache_dir if cache_dir is not None else _CACHE_DIR
    if not d.exists():
        return 0
    count = 0
    for p in d.glob("*.json"):
        p.unlink()
        count += 1
    return count
