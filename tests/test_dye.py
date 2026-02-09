"""Tests for the Dye enum."""

from __future__ import annotations

from biocompute.dye import Dye


class TestDye:
    def test_values(self) -> None:
        assert Dye.RED.value == "red_dye"
        assert Dye.GREEN.value == "green_dye"
        assert Dye.BLUE.value == "blue_dye"

    def test_str_serialization(self) -> None:
        assert str(Dye.RED) == "Dye.RED"
        assert Dye.RED == "red_dye"

    def test_is_str_subclass(self) -> None:
        assert isinstance(Dye.RED, str)

    def test_members(self) -> None:
        assert set(Dye) == {Dye.RED, Dye.GREEN, Dye.BLUE}
