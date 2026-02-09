"""Dye definitions for the biocompute client library."""

from __future__ import annotations

from enum import Enum


class Dye(str, Enum):
    """Available dyes for well operations."""

    RED = "red_dye"
    GREEN = "green_dye"
    BLUE = "blue_dye"
