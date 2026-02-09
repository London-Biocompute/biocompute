"""Tests for the Well data builder."""

from __future__ import annotations

from biocompute.dye import Dye
from biocompute.well import Well


class TestWell:
    def test_no_args_constructor(self) -> None:
        well = Well()
        assert well.ops == []

    def test_fill(self) -> None:
        well = Well()
        well.fill(Dye.RED, 50.0)

        assert len(well.ops) == 1
        assert well.ops[0] == {"op": "fill", "reagent": "red_dye", "volume": 50.0}

    def test_mix(self) -> None:
        well = Well()
        well.mix()

        assert len(well.ops) == 1
        assert well.ops[0] == {"op": "mix"}

    def test_image(self) -> None:
        well = Well()
        well.image()

        assert len(well.ops) == 1
        assert well.ops[0] == {"op": "image"}

    def test_chaining(self) -> None:
        well = Well()
        result = well.fill(Dye.RED, 50.0).mix().image()
        assert result is well
        assert len(well.ops) == 3

    def test_full_chain_ops(self) -> None:
        well = Well().fill(Dye.RED, 50.0).fill(Dye.GREEN, 30.0).mix().image()
        assert well.ops == [
            {"op": "fill", "reagent": "red_dye", "volume": 50.0},
            {"op": "fill", "reagent": "green_dye", "volume": 30.0},
            {"op": "mix"},
            {"op": "image"},
        ]

    def test_multiple_wells_independent(self) -> None:
        w0 = Well().fill(Dye.RED, 50.0)
        w1 = Well().fill(Dye.BLUE, 30.0)

        assert len(w0.ops) == 1
        assert len(w1.ops) == 1
        assert w0.ops[0]["reagent"] == "red_dye"
        assert w1.ops[0]["reagent"] == "blue_dye"
