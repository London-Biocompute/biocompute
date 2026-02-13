"""Tests for the Client API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from biocompute import cache
from biocompute.client import Client
from biocompute.exceptions import BiocomputeError
from biocompute.reagent import red_dye
from biocompute.well import wells


class TestClient:
    """Tests for Client construction and validation."""

    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="Missing credentials"):
            Client(api_key="sk_test", base_url="")

    def test_rejects_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from biocompute import client as client_mod

        monkeypatch.setattr(client_mod, "_load_config", lambda: {})
        with pytest.raises(BiocomputeError, match="Missing credentials"):
            Client(base_url="http://localhost:9999")

    def test_submit_rejects_empty_experiment(self) -> None:
        def empty() -> None:
            pass

        client = Client(api_key="sk_test", base_url="http://localhost:9999")
        with pytest.raises(BiocomputeError, match="no operations"):
            client.submit(empty)
        client.close()

    def test_context_manager(self) -> None:
        with Client(api_key="sk_test", base_url="http://localhost:9999") as client:
            assert client._api_key == "sk_test"


def _experiment() -> None:
    """A minimal experiment for testing."""
    for w in wells(count=1):
        w.fill(50.0, red_dye)


def _job_response(job_id: str = "job-1", status: str = "complete") -> dict[str, Any]:
    return {"id": job_id, "status": status, "result_data": {"score": 0.8}, "error_message": None}


class TestCachedSubmit:
    """Tests that Client.submit() uses the cache correctly."""

    @pytest.fixture(autouse=True)
    def _use_tmp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.cache_dir = tmp_path / "cache"
        monkeypatch.setattr(cache, "_CACHE_DIR", self.cache_dir)

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True, assert_all_responses_were_requested=False)
    def test_cache_hit_skips_http(self, httpx_mock: HTTPXMock) -> None:
        """A completed cache entry should return immediately without HTTP calls."""
        # Pre-populate the cache by doing a first submit
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs", json={"id": "job-1"}, method="POST")
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs/job-1", json=_job_response())

        client = Client(api_key="sk", base_url="http://test:9999")
        result1 = client.submit(_experiment)
        assert result1.status == "complete"

        # Second submit should not make any HTTP calls
        result2 = client.submit(_experiment)
        assert result2.status == "complete"
        assert result2.experiment_id == "job-1"
        assert result2.result_data == {"score": 0.8}

        # Verify only 2 HTTP requests were made (POST + GET poll), not 4
        assert len(httpx_mock.get_requests()) == 2
        client.close()

    def test_pending_entry_resumes_poll(self, httpx_mock: HTTPXMock) -> None:
        """A pending cache entry should poll the existing job_id."""
        # Manually write a pending cache entry
        client = Client(api_key="sk", base_url="http://test:9999")

        # First, trace to get the cache key
        from biocompute.client import _to_experiments
        from biocompute.trace import collect_trace

        trace = collect_trace(_experiment)
        experiments = _to_experiments(trace.ops)
        key = cache.cache_key("default", experiments)
        cache.put(
            key,
            cache.CacheEntry(
                challenge_id="default",
                experiments_hash=key,
                job_id="existing-job",
                status="pending",
            ),
        )

        # Mock only the poll response (no POST needed)
        httpx_mock.add_response(
            url="http://test:9999/api/v1/jobs/existing-job",
            json=_job_response(job_id="existing-job"),
        )

        result = client.submit(_experiment)
        assert result.experiment_id == "existing-job"
        assert result.status == "complete"

        # Verify only a GET was made, no POST
        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "GET"

        # Cache should now be updated to complete
        entry = cache.get(key)
        assert entry is not None
        assert entry.status == "complete"
        client.close()

    def test_failed_entry_retries(self, httpx_mock: HTTPXMock) -> None:
        """A failed cache entry should be removed and a new submission made."""
        client = Client(api_key="sk", base_url="http://test:9999")

        from biocompute.client import _to_experiments
        from biocompute.trace import collect_trace

        trace = collect_trace(_experiment)
        experiments = _to_experiments(trace.ops)
        key = cache.cache_key("default", experiments)
        cache.put(
            key,
            cache.CacheEntry(
                challenge_id="default",
                experiments_hash=key,
                job_id="old-job",
                status="failed",
                error="some error",
            ),
        )

        # Should POST a new job
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs", json={"id": "new-job"}, method="POST")
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs/new-job", json=_job_response(job_id="new-job"))

        result = client.submit(_experiment)
        assert result.experiment_id == "new-job"
        assert result.status == "complete"

        # Cache updated with new job
        entry = cache.get(key)
        assert entry is not None
        assert entry.job_id == "new-job"
        assert entry.status == "complete"
        client.close()

    def test_no_cache_mode(self, httpx_mock: HTTPXMock) -> None:
        """With use_cache=False, every submit hits the server."""
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs", json={"id": "j1"}, method="POST")
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs/j1", json=_job_response(job_id="j1"))
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs", json={"id": "j2"}, method="POST")
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs/j2", json=_job_response(job_id="j2"))

        client = Client(api_key="sk", base_url="http://test:9999", use_cache=False)
        r1 = client.submit(_experiment)
        r2 = client.submit(_experiment)
        assert r1.experiment_id == "j1"
        assert r2.experiment_id == "j2"
        assert len(httpx_mock.get_requests()) == 4
        client.close()
