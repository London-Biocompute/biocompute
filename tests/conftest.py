"""Shared fixtures for biocompute tests."""

from __future__ import annotations

import pytest

from biocompute.trace import _current_trace


@pytest.fixture(autouse=True)
def _clean_trace() -> None:  # type: ignore[misc]
    """Ensure no trace leaks between tests."""
    # Reset before test (in case a prior test leaked)
    token = _current_trace.set(None)
    yield  # type: ignore[misc]
    _current_trace.reset(token)
