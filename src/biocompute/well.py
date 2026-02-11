"""Well API for the biocompute client library."""

from __future__ import annotations

from typing import Iterator

from biocompute.ops import FillOp, ImageOp, MixOp
from biocompute.reagent import Reagent
from biocompute.trace import Trace, get_current_trace


class Well:
    """A well that captures operations during experiment tracing.

    Wells are created by the ``wells()`` generator inside an
    experiment function passed to ``client.submit()``. Operations
    like ``fill()``, ``mix()``, and ``image()`` are recorded into
    the trace.
    """

    def __init__(self, idx: int, trace: Trace) -> None:
        self._idx = idx
        self._trace = trace
        self._trace.update_well_count(idx)

    @property
    def index(self) -> int:
        """Return the well index."""
        return self._idx

    def fill(self, vol: float, reagent: Reagent) -> Well:
        """Fill this well with a volume of reagent.

        Args:
            vol: Volume in microliters.
            reagent: The reagent to fill with.

        Returns:
            self for method chaining.
        """
        self._trace.emit(FillOp(well_idx=self._idx, reagent=reagent, volume_ul=vol))
        return self

    def mix(self) -> Well:
        """Mix the contents of this well.

        Returns:
            self for method chaining.
        """
        self._trace.emit(MixOp(well_idx=self._idx))
        return self

    def image(self) -> Well:
        """Capture an image of this well.

        Returns:
            self for method chaining.
        """
        self._trace.emit(ImageOp(well_idx=self._idx))
        return self


def wells(count: int = 96) -> Iterator[Well]:
    """Yield wells for experiment definition.

    Each call allocates the next *count* unique well indices,
    so multiple ``wells()`` calls within the same trace produce
    non-overlapping wells automatically.

    Args:
        count: Number of wells to use.

    Yields:
        Well objects with unique, auto-incrementing indices.

    Raises:
        BiocomputeError: If called outside of client.submit().
    """
    trace = get_current_trace()
    for i in trace.allocate_wells(count):
        yield Well(i, trace)
