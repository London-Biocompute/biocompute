"""Client for submitting experiments to a server."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

from biocompute.exceptions import BiocomputeError
from biocompute.ops import op_to_dict
from biocompute.trace import TracedOp, collect_trace

CONFIG_FILE = Path.home() / ".lbc" / "config.toml"
DEFAULT_BASE_URL = os.environ.get("LBC_BASE_URL", "https://lbc.fly.dev")


def save_config(config: dict[str, str]) -> None:
    """Save config to ~/.lbc/config.toml."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{k} = "{v}"' for k, v in config.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n")


def _load_config() -> dict[str, str]:
    """Load config from ~/.lbc/config.toml."""
    if not CONFIG_FILE.exists():
        return {}
    config: dict[str, str] = {}
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip().strip('"')
    return config


@dataclass
class SubmissionResult:
    """Result of a protocol submission."""

    job_id: str
    status: str
    result_data: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_job_data(cls, data: dict[str, Any]) -> SubmissionResult:
        return cls(
            job_id=data["id"],
            status=data.get("status", "unknown"),
            result_data=data.get("result_data"),
            error=data.get("error_message"),
            raw=data,
        )

    @property
    def well_images(self) -> dict[str, str]:
        """Well label -> base64 data URI image, from a successful result."""
        if isinstance(self.result_data, dict):
            images: dict[str, str] = self.result_data.get("well_images", {})
            return images
        return {}

    @property
    def duration_seconds(self) -> float:
        """Execution duration in seconds, from a successful result."""
        if isinstance(self.result_data, dict):
            val: float = self.result_data.get("duration_seconds", 0.0)
            return val
        return 0.0


class Client:
    """Client for submitting experiments to a biocompute server.

    Usage::

        def my_experiment():
            for well in wells(count=96):
                well.fill(100.0, water)

        client = Client(api_key="sk_...", base_url="https://...")
        result = client.submit(my_experiment)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        config = _load_config() if (api_key is None or base_url is None) else {}

        api_key = api_key or config.get("api_key", "")
        base_url = base_url or config.get("base_url", "") or DEFAULT_BASE_URL

        if not api_key or not base_url:
            raise BiocomputeError(
                "Missing credentials. Either pass api_key and base_url explicitly, "
                "or run `lbc login` to configure them."
            )

        self._api_key = api_key
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

    def user(self) -> dict[str, Any]:
        """Get the authenticated user's info."""
        resp = self._client.get(f"{self._base_url}/api/v1/user")
        _check(resp)
        data: dict[str, Any] = resp.json()
        return data

    def submit(self, fn: Callable[[], None]) -> SubmissionResult:
        """Submit an experiment function and poll for results.

        Args:
            fn: A callable that defines well operations.

        Returns:
            SubmissionResult with job data.
        """
        job_data = self.submit_async(fn)
        return self._poll(job_data["id"])

    def submit_async(self, fn: Callable[[], None]) -> dict[str, Any]:
        """Submit an experiment and return the job data without polling.

        Args:
            fn: A callable that defines well operations.

        Returns:
            Job data dict from the server.
        """
        trace = collect_trace(fn)
        if not trace.ops:
            raise BiocomputeError("Experiment has no operations. Call well.fill(), well.mix(), etc. in the experiment function.")

        experiments = _to_experiments(trace.ops)

        resp = self._client.post(
            f"{self._base_url}/api/v1/jobs",
            json={
                "experiments": experiments,
            },
        )
        _check(resp)
        data: dict[str, Any] = resp.json()
        return data

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all jobs for this challenge.

        Returns:
            List of job summaries from the server.
        """
        resp = self._client.get(f"{self._base_url}/api/v1/jobs")
        _check(resp)
        data: list[dict[str, Any]] = resp.json()
        return data

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Get details for a single job.

        Args:
            job_id: The job ID.

        Returns:
            Job details from the server.
        """
        resp = self._client.get(f"{self._base_url}/api/v1/jobs/{job_id}")
        _check(resp)
        data: dict[str, Any] = resp.json()
        return data

    def enrollment(self) -> dict[str, Any]:
        """Get the authenticated user's active enrollment."""
        resp = self._client.get(
            f"{self._base_url}/api/v1/user/enrollment",
        )
        _check(resp)
        data: dict[str, Any] = resp.json()
        return data

    def target(self) -> str:
        """Get the target image as base64 for this challenge."""
        data = self.enrollment()
        b64: str = data["target_image_base64"]
        return b64

    def leaderboard(self) -> list[dict[str, Any]]:
        """Get the public leaderboard for the user's active challenge."""
        data = self.enrollment()
        challenge_id = data["challenge_id"]
        resp = self._client.get(
            f"{self._base_url}/api/v1/challenges/{challenge_id}/leaderboard",
        )
        _check(resp)
        entries: list[dict[str, Any]] = resp.json()["entries"]
        return entries

    def _poll(self, job_id: str) -> SubmissionResult:
        """Poll for job completion with backoff (no output)."""
        start = time.monotonic()
        delay = 1.0

        while True:
            elapsed = time.monotonic() - start
            if elapsed > self._timeout:
                raise BiocomputeError(f"Job did not complete within {self._timeout}s")

            data = self.get_job(job_id)
            status = data.get("status", "unknown")

            if status in ("complete", "failed"):
                return SubmissionResult.from_job_data(data)

            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)


def _check(resp: httpx.Response) -> None:
    """Raise BiocomputeError on non-success responses."""
    if resp.is_success:
        return
    try:
        data: dict[str, Any] = resp.json()
        detail = data.get("detail")
        if detail:
            raise BiocomputeError(str(detail))
        raise BiocomputeError(resp.text)
    except BiocomputeError:
        raise
    except Exception:
        raise BiocomputeError(resp.text) from None


def _to_experiments(ops: list[TracedOp]) -> list[list[dict[str, Any]]]:
    """Group traced ops by well into experiments for the job server."""
    by_well: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for traced in ops:
        by_well[traced.op.well_idx].append(op_to_dict(traced.op))
    return [by_well[i] for i in sorted(by_well)]
