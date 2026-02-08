"""Tests for operation serialization."""

from __future__ import annotations

from biocompute.ops import FillOp, ImageOp, MixOp, op_to_dict
from biocompute.reagent import Reagent, red_dye, water


class TestOpToDict:
    """Tests for op_to_dict serialization."""

    def test_fill_op(self) -> None:
        op = FillOp(well_idx=0, reagent=red_dye, volume_ul=50.0)
        d = op_to_dict(op)
        assert d == {"type": "fill", "well_idx": 0, "reagent": "red_dye", "volume_ul": 50.0}

    def test_mix_op(self) -> None:
        op = MixOp(well_idx=3)
        d = op_to_dict(op)
        assert d == {"type": "mix", "well_idx": 3}

    def test_image_op(self) -> None:
        op = ImageOp(well_idx=7)
        d = op_to_dict(op)
        assert d == {"type": "image", "well_idx": 7}

    def test_ops_are_frozen(self) -> None:
        op = FillOp(well_idx=0, reagent=water, volume_ul=100.0)
        try:
            op.well_idx = 1  # type: ignore[misc]
            raise AssertionError("Should have raised")  # pragma: no cover
        except AttributeError:
            pass

    def test_fill_op_stores_reagent_object(self) -> None:
        custom = Reagent("custom")
        op = FillOp(well_idx=0, reagent=custom, volume_ul=10.0)
        assert op.reagent is custom
        assert op.reagent.name == "custom"
