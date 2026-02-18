"""Tests for the Client API."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from biocompute.client import Client, SubmissionResult
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


# Minimal valid 1x1 white PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestWellImages:
    """Tests for SubmissionResult.well_images saving PNGs to disk."""

    def test_saves_pngs_and_returns_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import biocompute.client as client_mod

        monkeypatch.setattr(client_mod, "IMAGES_DIR", tmp_path)

        data_uri = "data:image/png;base64," + base64.b64encode(_TINY_PNG).decode()
        result = SubmissionResult(
            job_id="test-job-123",
            status="complete",
            result_data={"well_images": {"A1": data_uri, "B2": data_uri}},
        )

        images = result.well_images
        assert set(images.keys()) == {"A1", "B2"}
        for well_label, path in images.items():
            assert isinstance(path, Path)
            assert path.exists()
            assert path.name == f"{well_label}.png"
            content = path.read_bytes()
            assert content[:4] == b"\x89PNG"

    def test_caches_on_second_access(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import biocompute.client as client_mod

        monkeypatch.setattr(client_mod, "IMAGES_DIR", tmp_path)

        data_uri = "data:image/png;base64," + base64.b64encode(_TINY_PNG).decode()
        result = SubmissionResult(
            job_id="test-job-cache",
            status="complete",
            result_data={"well_images": {"A1": data_uri}},
        )

        first = result.well_images
        second = result.well_images
        assert first is second

    def test_empty_when_no_images(self) -> None:
        result = SubmissionResult(job_id="x", status="complete", result_data={"score": 1.0})
        assert result.well_images == {}

    def test_empty_when_no_result_data(self) -> None:
        result = SubmissionResult(job_id="x", status="failed")
        assert result.well_images == {}
