"""Shared fixtures for biocompute tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from biocompute.trace import _current_trace


@pytest.fixture(autouse=True)
def _clean_trace() -> Generator[None]:
    """Ensure no trace leaks between tests."""
    token = _current_trace.set(None)
    yield
    _current_trace.reset(token)
