"""Operation dataclasses for the biocompute client library.

These represent the atomic well operations that get serialized
and sent to the competition server.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from biocompute.reagent import Reagent


@dataclass(frozen=True)
class FillOp:
    """Fill a well with a reagent."""

    well_idx: int
    reagent: Reagent
    volume_ul: float


@dataclass(frozen=True)
class MixOp:
    """Mix contents of a well."""

    well_idx: int


@dataclass(frozen=True)
class ImageOp:
    """Capture an image of a well."""

    well_idx: int


Op = FillOp | MixOp | ImageOp


def op_to_dict(op: Op) -> dict[str, str | int | float]:
    """Serialize an operation to a JSON-compatible dict."""
    if isinstance(op, FillOp):
        return {"type": "fill", "well_idx": op.well_idx, "reagent": op.reagent.name, "volume_ul": op.volume_ul}
    elif isinstance(op, MixOp):
        return {"type": "mix", "well_idx": op.well_idx}
    elif isinstance(op, ImageOp):
        return {"type": "image", "well_idx": op.well_idx}
    raise ValueError(f"Unknown op type: {op}")  # pragma: no cover
