"""Internal trace context for capturing well operations."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

from biocompute.exceptions import BiocomputeError
from biocompute.ops import Op

_current_trace: ContextVar[Trace | None] = ContextVar("biocompute_trace", default=None)


def get_current_trace() -> Trace:
    """Get the active trace context.

    Raises:
        BiocomputeError: If no active protocol trace context.
    """
    t = _current_trace.get()
    if t is None:
        raise BiocomputeError("wells() called outside of a @protocol function")
    return t


@dataclass
class TracedOp:
    """An operation wrapped with a unique ID assigned during tracing.

    The ID is used as the node key in dependency DAGs and
    device assignment plans.
    """

    id: int
    op: Op


@dataclass
class Trace:
    """Collects operations during experiment definition.

    Each emitted op is wrapped in a TracedOp with a unique
    auto-incrementing ID.
    """

    ops: list[TracedOp] = field(default_factory=list)
    well_count: int = 0
    _next_id: int = field(default=0, repr=False)
    _next_well: int = field(default=0, repr=False)

    @classmethod
    def from_ops(cls, traced_ops: list[TracedOp], well_count: int = 0) -> Trace:
        """Create a Trace from existing TracedOps with correct _next_id.

        Use this when constructing a Trace from already-ID'd ops
        (e.g., after collapse transformations) to ensure _next_id
        won't conflict if emit() is called later.

        Args:
            traced_ops: List of TracedOps (should already have IDs assigned)
            well_count: Total number of wells accessed

        Returns:
            A Trace with _next_id set to max(op.id) + 1
        """
        next_id = max((t.id for t in traced_ops), default=-1) + 1
        return cls(ops=traced_ops, well_count=well_count, _next_id=next_id)

    def emit(self, op: Op) -> int:
        """Record an operation, wrapping it in a TracedOp with a unique ID.

        Args:
            op: The operation to record.

        Returns:
            The assigned op ID.
        """
        traced = TracedOp(id=self._next_id, op=op)
        self._next_id += 1
        self.ops.append(traced)
        return traced.id

    def allocate_wells(self, count: int) -> range:
        """Allocate the next `count` well indices.

        Each call returns a non-overlapping range so multiple
        ``wells()`` calls within the same trace get unique indices.
        """
        start = self._next_well
        self._next_well += count
        self.well_count = max(self.well_count, self._next_well)
        return range(start, start + count)

    def update_well_count(self, idx: int) -> None:
        """Update the total well count based on accessed index."""
        self.well_count = max(self.well_count, idx + 1)
