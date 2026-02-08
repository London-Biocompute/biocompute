"""Tests for Well and wells() API."""

from __future__ import annotations

import pytest

from biocompute.exceptions import BiocomputeError
from biocompute.ops import FillOp, ImageOp, MixOp
from biocompute.reagent import Reagent, red_dye
from biocompute.trace import Trace, _current_trace
from biocompute.well import Well, wells


class TestWells:
    """Tests for the wells() generator."""

    def test_yields_correct_count(self) -> None:
        trace = Trace()
        _current_trace.set(trace)
        ws = list(wells(count=8))
        assert len(ws) == 8

    def test_well_indices(self) -> None:
        trace = Trace()
        _current_trace.set(trace)
        ws = list(wells(count=4))
        assert [w.index for w in ws] == [0, 1, 2, 3]

    def test_updates_well_count(self) -> None:
        trace = Trace()
        _current_trace.set(trace)
        list(wells(count=8))
        assert trace.well_count == 8

    def test_raises_without_trace(self) -> None:
        with pytest.raises(BiocomputeError, match="without an active Competition"):
            list(wells(count=1))


class TestWell:
    """Tests for Well operations."""

    def test_fill(self) -> None:
        trace = Trace()
        well = Well(0, trace)
        well.fill(vol=50.0, reagent=red_dye)

        assert len(trace.ops) == 1
        op = trace.ops[0].op
        assert isinstance(op, FillOp)
        assert op.well_idx == 0
        assert op.reagent is red_dye
        assert op.volume_ul == 50.0

    def test_mix(self) -> None:
        trace = Trace()
        well = Well(0, trace)
        well.mix()

        assert len(trace.ops) == 1
        assert isinstance(trace.ops[0].op, MixOp)
        assert trace.ops[0].op.well_idx == 0

    def test_image(self) -> None:
        trace = Trace()
        well = Well(0, trace)
        well.image()

        assert len(trace.ops) == 1
        assert isinstance(trace.ops[0].op, ImageOp)
        assert trace.ops[0].op.well_idx == 0

    def test_chaining(self) -> None:
        trace = Trace()
        well = Well(0, trace)
        result = well.fill(vol=50.0, reagent=red_dye).mix().image()
        assert result is well
        assert len(trace.ops) == 3

    def test_custom_reagent(self) -> None:
        trace = Trace()
        well = Well(0, trace)
        my_reagent = Reagent("custom_stuff")
        well.fill(vol=10.0, reagent=my_reagent)

        op = trace.ops[0].op
        assert isinstance(op, FillOp)
        assert op.reagent is my_reagent

    def test_multiple_wells_independent(self) -> None:
        trace = Trace()
        w0 = Well(0, trace)
        w1 = Well(1, trace)
        w0.fill(vol=50.0, reagent=red_dye)
        w1.fill(vol=30.0, reagent=red_dye)

        assert len(trace.ops) == 2
        assert trace.ops[0].op.well_idx == 0
        assert trace.ops[1].op.well_idx == 1
        assert trace.well_count == 2
