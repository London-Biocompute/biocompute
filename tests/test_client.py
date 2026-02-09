"""Tests for the Client."""

from __future__ import annotations

import json

import pytest

from biocompute.client import Client, LeaderboardEntry, SubmissionResult
from biocompute.dye import Dye
from biocompute.exceptions import BiocomputeError
from biocompute.well import Well

URL = "http://test.local"


def _job_response(
    job_id: str = "job-1",
    challenge_id: str = "c1",
    status: str = "complete",
    **extra: object,
) -> dict:
    """Build a minimal valid JobResponse."""
    resp: dict = {
        "id": job_id,
        "challenge_id": challenge_id,
        "status": status,
        "experiments": [],
        "wells_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    resp.update(extra)
    return resp


class TestClientInit:
    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Client(api_key="sk_test", base_url="")


class TestSubmit:
    def test_rejects_empty_wells(self) -> None:
        client = Client(api_key="sk_test", base_url=URL)
        with pytest.raises(BiocomputeError, match="No wells provided"):
            client.submit("challenge-1", [])

    def test_experiments_structure(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            json=_job_response(status="pending"),
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(wells_count=2),
        )

        wells = [
            Well().fill(Dye.RED, 50.0).mix().image(),
            Well().fill(Dye.GREEN, 30.0).image(),
        ]
        client = Client(api_key="sk_test", base_url=URL)
        client.submit("challenge-1", wells)

        payload = json.loads(httpx_mock.get_requests()[0].content)

        assert payload["challenge_id"] == "challenge-1"
        assert "well_count" not in payload
        assert "ops" not in payload

        # experiments is a list of lists — one per well
        experiments = payload["experiments"]
        assert len(experiments) == 2
        assert len(experiments[0]) == 3  # fill, mix, image
        assert len(experiments[1]) == 2  # fill, image

    def test_serializes_fill_op(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            json=_job_response(status="pending"),
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(wells_count=1),
        )

        wells = [Well().fill(Dye.RED, 50.0)]
        client = Client(api_key="sk_test", base_url=URL)
        client.submit("c1", wells)

        payload = json.loads(httpx_mock.get_requests()[0].content)
        op = payload["experiments"][0][0]
        assert op == {"op": "fill", "reagent": "red_dye", "volume": 50.0}

    def test_serializes_mix_and_image_ops(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            json=_job_response(status="pending"),
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(wells_count=1),
        )

        wells = [Well().mix().image()]
        client = Client(api_key="sk_test", base_url=URL)
        client.submit("c1", wells)

        payload = json.loads(httpx_mock.get_requests()[0].content)
        assert payload["experiments"][0][0] == {"op": "mix"}
        assert payload["experiments"][0][1] == {"op": "image"}

    def test_polls_until_complete(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            json=_job_response(status="pending"),
            status_code=201,
        )
        # First poll: still pending
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(status="pending"),
        )
        # Second poll: complete
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(wells_count=1, result_data={"score": 0.9}),
        )

        wells = [Well().fill(Dye.RED, 50.0).image()]
        client = Client(api_key="sk_test", base_url=URL, timeout=10.0)
        result = client.submit("c1", wells)

        assert isinstance(result, SubmissionResult)
        assert result.id == "job-1"
        assert result.challenge_id == "c1"
        assert result.status == "complete"
        assert result.result_data == {"score": 0.9}

    def test_raises_on_job_failure(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            json=_job_response(status="pending"),
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs/job-1",
            method="GET",
            json=_job_response(status="failed", error_message="bad input"),
        )

        wells = [Well().fill(Dye.RED, 50.0)]
        client = Client(api_key="sk_test", base_url=URL)
        with pytest.raises(BiocomputeError, match="failed.*bad input"):
            client.submit("c1", wells)

    def test_raises_on_http_error(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/jobs",
            method="POST",
            status_code=500,
            json={"message": "server error"},
        )

        wells = [Well().fill(Dye.RED, 50.0)]
        client = Client(api_key="sk_test", base_url=URL)
        with pytest.raises(BiocomputeError, match="HTTP 500"):
            client.submit("c1", wells)


class TestGetTarget:
    def test_returns_target_image(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/challenges/c1/enrollment",
            method="GET",
            json={
                "id": "enroll-1",
                "challenge_id": "c1",
                "target_image_base64": "iVBOR...",
                "wells_consumed": 0,
                "wells_limit": 100,
                "best_score": None,
                "created_at": "2025-01-01T00:00:00Z",
            },
        )

        client = Client(api_key="sk_test", base_url=URL)
        target = client.get_target("c1")

        assert target == "iVBOR..."

    def test_raises_on_http_error(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/challenges/c1/enrollment",
            method="GET",
            status_code=404,
            json={"message": "not found"},
        )

        client = Client(api_key="sk_test", base_url=URL)
        with pytest.raises(BiocomputeError, match="HTTP 404"):
            client.get_target("c1")


class TestLeaderboard:
    def test_returns_entries(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=f"{URL}/api/v1/challenges/c1/leaderboard",
            method="GET",
            json={
                "challenge_id": "c1",
                "entries": [
                    {"rank": 1, "user_name": "alice", "wells_consumed": 50, "best_score": 0.99},
                    {"rank": 2, "user_name": "bob", "wells_consumed": 75, "best_score": 0.95},
                ],
            },
        )

        client = Client(api_key="sk_test", base_url=URL)
        entries = client.leaderboard("c1")

        assert len(entries) == 2
        assert isinstance(entries[0], LeaderboardEntry)
        assert entries[0].rank == 1
        assert entries[0].user_name == "alice"
        assert entries[0].wells_consumed == 50
        assert entries[0].best_score == 0.99
        assert entries[1].rank == 2
        assert entries[1].user_name == "bob"
