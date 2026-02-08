"""Reagent definitions for the biocompute client library."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reagent:
    """A named reagent that can be used in well operations.

    This is the base reagent type shared across the biocompute ecosystem.
    """

    name: str

    def __str__(self) -> str:
        return self.name


# Built-in reagents for the color-match competition
red_dye = Reagent("red_dye")
green_dye = Reagent("green_dye")
blue_dye = Reagent("blue_dye")
water = Reagent("water")
