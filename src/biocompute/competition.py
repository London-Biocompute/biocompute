"""Competition client for submitting experiments to the server."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

import httpx

from biocompute.exceptions import BiocomputeError
from biocompute.ops import op_to_dict
from biocompute.trace import Trace, _current_trace


@dataclass
class WellResult:
    """Result data for a single well."""

    well_idx: int
    img_b64: str | None = None
    score: float | None = None


@dataclass
class SubmissionResult:
    """Result of a competition submission."""

    job_id: str
    status: str
    wells: list[WellResult] = field(default_factory=list)
    score: float | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Competition:
    """Competition client. Create, record well ops, then submit.

    Can be used as a context manager to ensure cleanup::

        with Competition(api_key="sk_...") as comp:
            for well in wells(count=4):
                well.fill(vol=50.0, reagent=red_dye)
            results = comp.submit()
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
        if _current_trace.get() is not None:
            raise BiocomputeError("Another Competition is already active")

        self._api_key = api_key
        self._challenge_id = challenge_id
        self._base_url = base_url
        self._timeout = timeout
        self._trace = Trace()
        self._token = _current_trace.set(self._trace)
        self._closed = False
        self._submitted = False
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def __enter__(self) -> Competition:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release the trace context and HTTP client."""
        if not self._closed:
            self._closed = True
            if _current_trace.get() is self._trace:
                _current_trace.reset(self._token)
            self._client.close()

    def __del__(self) -> None:
        if hasattr(self, "_closed"):
            self.close()

    def submit(self) -> SubmissionResult:
        """Submit traced operations and poll for results."""
        if self._submitted:
            raise BiocomputeError("Already submitted. Create a new Competition for another submission.")
        self._submitted = True
        self._closed = True

        _current_trace.reset(self._token)
        trace = self._trace

        if not trace.ops:
            raise BiocomputeError("No operations recorded. Call well.fill(), well.mix(), etc. before submitting.")

        payload: dict[str, Any] = {
            "action": "submit",
            "challenge_id": self._challenge_id,
            "well_count": trace.well_count,
            "ops": [op_to_dict(traced.op) for traced in trace.ops],
        }

        resp = self._client.post(self._base_url, json=payload)
        _check(resp)
        data: dict[str, Any] = resp.json()
        job_id: str = data["job_id"]

        return self._poll(job_id)

    def target(self) -> str:
        """Get the target image URL for this challenge."""
        resp = self._client.post(
            self._base_url,
            json={"action": "target", "challenge_id": self._challenge_id},
        )
        _check(resp)
        url: str = resp.json()["image_url"]
        return url

    def leaderboard(self) -> list[dict[str, Any]]:
        """Get the public leaderboard for this challenge."""
        resp = self._client.post(
            self._base_url,
            json={"action": "leaderboard", "challenge_id": self._challenge_id},
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

            resp = self._client.post(
                self._base_url,
                json={"action": "results", "job_id": job_id},
            )
            _check(resp)
            data: dict[str, Any] = resp.json()

            status = data.get("status", "unknown")
            if status == "complete":
                return _parse_result(job_id, data)
            elif status == "failed":
                raise BiocomputeError(f"Job {job_id} failed: {data.get('error', 'unknown error')}")

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


def _parse_result(job_id: str, data: dict[str, Any]) -> SubmissionResult:
    """Parse the results response."""
    well_results = [
        WellResult(well_idx=w["well_idx"], img_b64=w.get("img_b64"), score=w.get("score"))
        for w in data.get("wells", [])
    ]
    return SubmissionResult(
        job_id=job_id,
        status="complete",
        wells=well_results,
        score=data.get("score"),
        raw=data,
    )
