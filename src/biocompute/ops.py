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


def op_to_dict(op: Op) -> dict[str, str | float]:
    """Serialize an operation to a JSON-compatible dict."""
    if isinstance(op, FillOp):
        return {"op": "fill", "reagent": op.reagent.name, "volume": op.volume_ul}
    elif isinstance(op, MixOp):
        return {"op": "mix"}
    elif isinstance(op, ImageOp):
        return {"op": "image"}
    raise ValueError(f"Unknown op type: {op}")  # pragma: no cover
