"""Tests for the Client API."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_httpx import HTTPXMock

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


class TestSubmit:
    """Tests that Client.submit() hits the server correctly."""

    def test_submit_and_poll(self, httpx_mock: HTTPXMock) -> None:
        """Every submit hits the server and polls for results."""
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs", json={"id": "j1"}, method="POST")
        httpx_mock.add_response(url="http://test:9999/api/v1/jobs/j1", json=_job_response(job_id="j1"))

        client = Client(api_key="sk", base_url="http://test:9999")
        result = client.submit(_experiment)
        assert result.job_id == "j1"
        assert result.status == "complete"
        assert len(httpx_mock.get_requests()) == 2
        client.close()
