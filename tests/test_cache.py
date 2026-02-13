"""Tests for the local file cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from biocompute.cache import CacheEntry, cache_key, clear, get, put, remove


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


class TestCacheKey:
    """cache_key is deterministic and sensitive to input changes."""

    def test_deterministic(self) -> None:
        experiments: list[list[dict[str, Any]]] = [[{"op": "fill", "reagent": "red_dye", "volume": 50.0}]]
        k1 = cache_key("chal1", experiments)
        k2 = cache_key("chal1", experiments)
        assert k1 == k2

    def test_different_challenge_id(self) -> None:
        experiments: list[list[dict[str, Any]]] = [[{"op": "mix"}]]
        k1 = cache_key("chal1", experiments)
        k2 = cache_key("chal2", experiments)
        assert k1 != k2

    def test_different_experiments(self) -> None:
        k1 = cache_key("c", [[{"op": "mix"}]])
        k2 = cache_key("c", [[{"op": "image"}]])
        assert k1 != k2

    def test_order_matters(self) -> None:
        k1 = cache_key("c", [[{"op": "mix"}, {"op": "image"}]])
        k2 = cache_key("c", [[{"op": "image"}, {"op": "mix"}]])
        assert k1 != k2


class TestCacheRoundtrip:
    """get/put/remove lifecycle."""

    def test_get_missing_returns_none(self, cache_dir: Path) -> None:
        assert get("nonexistent", cache_dir=cache_dir) is None

    def test_put_then_get(self, cache_dir: Path) -> None:
        entry = CacheEntry(
            challenge_id="chal1",
            experiments_hash="abc123",
            job_id="job-42",
            status="complete",
            result={"score": 0.9},
        )
        put("abc123", entry, cache_dir=cache_dir)
        loaded = get("abc123", cache_dir=cache_dir)
        assert loaded is not None
        assert loaded.job_id == "job-42"
        assert loaded.status == "complete"
        assert loaded.result == {"score": 0.9}
        assert loaded.error is None

    def test_remove(self, cache_dir: Path) -> None:
        entry = CacheEntry(
            challenge_id="c",
            experiments_hash="k",
            job_id="j",
            status="pending",
        )
        put("k", entry, cache_dir=cache_dir)
        assert get("k", cache_dir=cache_dir) is not None
        remove("k", cache_dir=cache_dir)
        assert get("k", cache_dir=cache_dir) is None

    def test_remove_missing_is_noop(self, cache_dir: Path) -> None:
        remove("does-not-exist", cache_dir=cache_dir)

    def test_clear(self, cache_dir: Path) -> None:
        for i in range(3):
            entry = CacheEntry(
                challenge_id="c",
                experiments_hash=f"k{i}",
                job_id=f"j{i}",
                status="complete",
            )
            put(f"k{i}", entry, cache_dir=cache_dir)
        removed = clear(cache_dir=cache_dir)
        assert removed == 3
        for i in range(3):
            assert get(f"k{i}", cache_dir=cache_dir) is None

    def test_clear_empty(self, cache_dir: Path) -> None:
        assert clear(cache_dir=cache_dir) == 0
