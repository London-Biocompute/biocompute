"""Client for submitting experiments to the biocompute server."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from biocompute.exceptions import BiocomputeError
from biocompute.well import Well


@dataclass
class SubmissionResult:
    """Result of a job submission (maps to server JobResponse)."""

    id: str
    challenge_id: str
    status: str
    wells_count: int = 0
    result_data: dict[str, Any] | list[Any] | None = None
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LeaderboardEntry:
    """A single entry on the challenge leaderboard."""

    rank: int
    user_name: str
    wells_consumed: int
    best_score: float
    raw: dict[str, Any] = field(default_factory=dict)


class Client:
    """Biocompute API client.

    Example::

        client = Client(api_key="sk_...", base_url="https://...")
        wells = [Well().fill(Dye.RED, 50.0).mix().image() for _ in range(25)]
        result = client.submit("challenge-id", wells)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 300.0,
    ) -> None:
        if not base_url:
            raise BiocomputeError("base_url is required")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def submit(self, challenge_id: str, wells: list[Well]) -> SubmissionResult:
        """Submit well operations and poll for results.

        Well indices are assigned from list position.

        Args:
            challenge_id: The challenge to submit to.
            wells: List of Well objects with recorded operations.

        Returns:
            SubmissionResult with job outcome.
        """
        if not wells:
            raise BiocomputeError("No wells provided.")

        experiments: list[list[dict[str, Any]]] = []
        for well in wells:
            well_ops: list[dict[str, Any]] = []
            for op in well.ops:
                serialized: dict[str, Any] = {"op": op["op"]}
                if op["op"] == "fill":
                    serialized["reagent"] = op["reagent"]
                    serialized["volume"] = op["volume"]
                well_ops.append(serialized)
            experiments.append(well_ops)

        payload: dict[str, Any] = {
            "challenge_id": challenge_id,
            "experiments": experiments,
        }

        resp = self._client.post(f"{self._base_url}/api/v1/jobs", json=payload)
        _check(resp)
        data: dict[str, Any] = resp.json()
        job_id: str = data["id"]

        return self._poll(job_id)

    def get_target(self, challenge_id: str) -> str:
        """Get the target image for a challenge.

        Args:
            challenge_id: The challenge ID.

        Returns:
            Base64-encoded target image string.
        """
        resp = self._client.get(f"{self._base_url}/api/v1/challenges/{challenge_id}/enrollment")
        _check(resp)
        data: dict[str, Any] = resp.json()
        target: str = data["target_image_base64"]
        return target

    def leaderboard(self, challenge_id: str) -> list[LeaderboardEntry]:
        """Get the leaderboard for a challenge.

        Args:
            challenge_id: The challenge ID.

        Returns:
            List of LeaderboardEntry objects.
        """
        resp = self._client.get(f"{self._base_url}/api/v1/challenges/{challenge_id}/leaderboard")
        _check(resp)
        data: dict[str, Any] = resp.json()
        entries: list[dict[str, Any]] = data["entries"]
        return [
            LeaderboardEntry(
                rank=e["rank"],
                user_name=e["user_name"],
                wells_consumed=e["wells_consumed"],
                best_score=e["best_score"],
                raw=e,
            )
            for e in entries
        ]

    def _poll(self, job_id: str) -> SubmissionResult:
        """Poll for job completion with backoff."""
        start = time.monotonic()
        delay = 1.0

        while True:
            elapsed = time.monotonic() - start
            if elapsed > self._timeout:
                raise BiocomputeError(f"Job {job_id} did not complete within {self._timeout}s")

            resp = self._client.get(f"{self._base_url}/api/v1/jobs/{job_id}")
            _check(resp)
            data: dict[str, Any] = resp.json()

            status = data.get("status", "unknown")
            if status == "complete":
                return _parse_result(data)
            elif status == "failed":
                raise BiocomputeError(
                    f"Job {job_id} failed: {data.get('error_message', 'unknown error')}"
                )

            print(".", end="", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)


def _check(resp: httpx.Response) -> None:
    """Raise BiocomputeError on non-success responses."""
    if resp.is_success:
        return
    try:
        data: dict[str, Any] = resp.json()
        msg = data.get("message", resp.text)
    except Exception:
        msg = resp.text
    raise BiocomputeError(f"HTTP {resp.status_code}: {msg}")


def _parse_result(data: dict[str, Any]) -> SubmissionResult:
    """Parse a completed job response."""
    return SubmissionResult(
        id=data["id"],
        challenge_id=data["challenge_id"],
        status=data.get("status", "complete"),
        wells_count=data.get("wells_count", 0),
        result_data=data.get("result_data"),
        error_message=data.get("error_message"),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        raw=data,
    )
