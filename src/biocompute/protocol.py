"""Protocol definition and capture."""

from __future__ import annotations

from typing import Callable, overload

from biocompute.trace import Trace, TracedOp, _current_trace


class Protocol:
    """A captured protocol — the result of executing a @protocol function.

    Contains the trace of all well operations and the well count.
    """

    def __init__(self, trace: Trace) -> None:
        self._trace = trace

    @property
    def trace(self) -> Trace:
        return self._trace

    @property
    def ops(self) -> list[TracedOp]:
        return self._trace.ops

    @property
    def well_count(self) -> int:
        return self._trace.well_count

    def __repr__(self) -> str:
        return f"Protocol(ops={len(self.ops)}, wells={self.well_count})"


def collect_trace(fn: Callable[[], None]) -> Trace:
    """Execute a function and collect its trace.

    Sets the ContextVar that wells() reads so the standard
    Well API works inside the function.
    """
    trace = Trace()
    token = _current_trace.set(trace)
    try:
        fn()
    finally:
        _current_trace.reset(token)
    return trace


@overload
def protocol(fn: Callable[[], None]) -> Protocol: ...
@overload
def protocol(fn: None = None) -> Callable[[Callable[[], None]], Protocol]: ...


def protocol(fn: Callable[[], None] | None = None) -> Protocol | Callable[[Callable[[], None]], Protocol]:
    """Capture a protocol function's well operations.

    Can be used as a decorator or called directly::

        @protocol
        def my_experiment():
            for well in wells(count=96):
                well.fill(100.0, water)

        # my_experiment is now a Protocol object

        # Or call directly:
        proto = protocol(some_function)
    """
    if fn is not None:
        return Protocol(collect_trace(fn))

    def decorator(f: Callable[[], None]) -> Protocol:
        return Protocol(collect_trace(f))

    return decorator
