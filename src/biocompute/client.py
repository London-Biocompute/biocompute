"""Client for submitting protocols to a server."""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

from biocompute.exceptions import BiocomputeError
from biocompute.ops import FillOp, ImageOp, MixOp
from biocompute.protocol import Protocol
from biocompute.trace import TracedOp


@dataclass
class SubmissionResult:
    """Result of a protocol submission."""

    job_id: str
    status: str
    result_data: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Client:
    """Client for submitting protocols to a biocompute server.

    Usage::

        @protocol
        def my_experiment():
            for well in wells(count=96):
                well.fill(100.0, water)

        client = Client(api_key="sk_...", base_url="https://...")
        result = client.submit(my_experiment)
    """

    def __init__(
        self,
        api_key: str,
        *,
        challenge_id: str = "default",
        base_url: str = "",
        timeout: float = 300.0,
    ) -> None:
        if not base_url:
            raise BiocomputeError("base_url is required")

        self._api_key = api_key
        self._challenge_id = challenge_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def submit(self, proto: Protocol) -> SubmissionResult:
        """Submit a protocol and poll for results.

        Args:
            proto: A Protocol object from the @protocol decorator.

        Returns:
            SubmissionResult with job data.
        """
        if not proto.ops:
            raise BiocomputeError("Protocol has no operations. Call well.fill(), well.mix(), etc. in the protocol function.")

        resp = self._client.post(
            f"{self._base_url}/api/v1/jobs",
            json={
                "challenge_id": self._challenge_id,
                "experiments": _to_experiments(proto.ops),
            },
        )
        _check(resp)
        job_id: str = resp.json()["id"]

        return self._poll(job_id)

    def target(self) -> str:
        """Get the target image as base64 for this challenge."""
        resp = self._client.get(
            f"{self._base_url}/api/v1/challenges/{self._challenge_id}/enrollment",
        )
        _check(resp)
        b64: str = resp.json()["target_image_base64"]
        return b64

    def leaderboard(self) -> list[dict[str, Any]]:
        """Get the public leaderboard for this challenge."""
        resp = self._client.get(
            f"{self._base_url}/api/v1/challenges/{self._challenge_id}/leaderboard",
        )
        _check(resp)
        entries: list[dict[str, Any]] = resp.json()["entries"]
        return entries

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
                raise BiocomputeError(f"Job {job_id} failed: {data.get('error_message', 'unknown error')}")

            print(".", end="", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)


def _check(resp: httpx.Response) -> None:
    """Raise BiocomputeError on non-success responses."""
    if resp.is_success:
        return
    try:
        data: dict[str, Any] = resp.json()
        msg = data.get("detail", resp.text)
    except Exception:
        msg = resp.text
    raise BiocomputeError(f"HTTP {resp.status_code}: {msg}")


def _parse_result(data: dict[str, Any]) -> SubmissionResult:
    """Parse a JobResponse into a SubmissionResult."""
    return SubmissionResult(
        job_id=data["id"],
        status=data["status"],
        result_data=data.get("result_data"),
        error=data.get("error_message"),
        raw=data,
    )


def _to_experiments(ops: list[TracedOp]) -> list[list[dict[str, Any]]]:
    """Group traced ops by well into experiments for the job server."""
    by_well: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for traced in ops:
        op = traced.op
        if isinstance(op, FillOp):
            by_well[op.well_idx].append({"op": "fill", "reagent": op.reagent.name, "volume": op.volume_ul})
        elif isinstance(op, MixOp):
            by_well[op.well_idx].append({"op": "mix"})
        elif isinstance(op, ImageOp):
            by_well[op.well_idx].append({"op": "image"})
    return [by_well[i] for i in sorted(by_well)]
