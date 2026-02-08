"""Tests for the Competition client."""

from __future__ import annotations

import pytest

from biocompute.competition import Competition
from biocompute.exceptions import BiocomputeError
from biocompute.ops import FillOp, ImageOp, MixOp
from biocompute.reagent import red_dye
from biocompute.trace import _current_trace
from biocompute.well import wells

URL = "http://localhost:9999"


class TestCompetitionTraceLifecycle:
    """Tests for Competition trace context management."""

    def test_creates_trace_context(self) -> None:
        with Competition(api_key="sk_test", base_url=URL) as comp:
            ws = list(wells(count=2))
            assert len(ws) == 2
            assert _current_trace.get() is comp._trace

    def test_records_operations(self) -> None:
        with Competition(api_key="sk_test", base_url=URL) as comp:
            for well in wells(count=2):
                well.fill(vol=50.0, reagent=red_dye)
                well.mix()
                well.image()

            assert len(comp._trace.ops) == 6
            assert isinstance(comp._trace.ops[0].op, FillOp)
            assert isinstance(comp._trace.ops[1].op, MixOp)
            assert isinstance(comp._trace.ops[2].op, ImageOp)

    def test_rejects_double_competition(self) -> None:
        with Competition(api_key="sk_test", base_url=URL):
            with pytest.raises(BiocomputeError, match="already active"):
                Competition(api_key="sk_test2", base_url=URL)

    def test_submit_rejects_empty(self) -> None:
        with Competition(api_key="sk_test", base_url=URL) as comp:
            with pytest.raises(BiocomputeError, match="No operations recorded"):
                comp.submit()

    def test_submit_rejects_double(self) -> None:
        with Competition(api_key="sk_test", base_url=URL) as comp:
            for well in wells(count=1):
                well.fill(vol=50.0, reagent=red_dye)
            comp._submitted = True
            comp._closed = True
            _current_trace.reset(comp._token)
            with pytest.raises(BiocomputeError, match="Already submitted"):
                comp.submit()

    def test_well_count_tracked(self) -> None:
        with Competition(api_key="sk_test", base_url=URL) as comp:
            list(wells(count=8))
            assert comp._trace.well_count == 8


class TestCompetitionContextManager:
    """Tests for context manager cleanup."""

    def test_cleans_up_on_exit(self) -> None:
        with Competition(api_key="sk_test", base_url=URL):
            assert _current_trace.get() is not None
        assert _current_trace.get() is None

    def test_cleans_up_on_exception(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            with Competition(api_key="sk_test", base_url=URL):
                raise ValueError("boom")
        assert _current_trace.get() is None

    def test_allows_new_competition_after_close(self) -> None:
        with Competition(api_key="sk_test", base_url=URL):
            list(wells(count=1))
        with Competition(api_key="sk_test", base_url=URL):
            ws = list(wells(count=2))
            assert len(ws) == 2


class TestCompetitionValidation:
    """Tests for input validation."""

    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Competition(api_key="sk_test", base_url="")

    def test_rejects_missing_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Competition(api_key="sk_test")
