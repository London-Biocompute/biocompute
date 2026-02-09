"""Well API for the biocompute client library."""

from __future__ import annotations

from typing import Any

from biocompute.dye import Dye


class Well:
    """A standalone data builder that records well operations.

    Operations are stored as plain dicts and serialized by Client.submit().

    Example::

        well = Well().fill(Dye.RED, 50.0).fill(Dye.GREEN, 30.0).mix().image()
    """

    def __init__(self) -> None:
        self._ops: list[dict[str, Any]] = []

    @property
    def ops(self) -> list[dict[str, Any]]:
        """Return the recorded operations."""
        return self._ops

    def fill(self, dye: Dye, volume: float) -> Well:
        """Fill this well with a volume of dye.

        Args:
            dye: The dye to fill with.
            volume: Volume in microliters.

        Returns:
            self for method chaining.
        """
        self._ops.append({"op": "fill", "reagent": dye.value, "volume": volume})
        return self

    def mix(self) -> Well:
        """Mix the contents of this well.

        Returns:
            self for method chaining.
        """
        self._ops.append({"op": "mix"})
        return self

    def image(self) -> Well:
        """Capture an image of this well.

        Returns:
            self for method chaining.
        """
        self._ops.append({"op": "image"})
        return self
