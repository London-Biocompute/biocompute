"""Tests for the Client and @protocol API."""

from __future__ import annotations

import pytest

from biocompute.client import Client
from biocompute.exceptions import BiocomputeError
from biocompute.ops import FillOp, ImageOp, MixOp
from biocompute.protocol import Protocol, protocol
from biocompute.reagent import red_dye
from biocompute.well import wells


class TestProtocolDecorator:
    """Tests for the @protocol decorator."""

    def test_captures_operations(self) -> None:
        @protocol
        def my_proto() -> None:
            for well in wells(count=2):
                well.fill(vol=50.0, reagent=red_dye)
                well.mix()
                well.image()

        assert isinstance(my_proto, Protocol)
        assert len(my_proto.ops) == 6
        assert isinstance(my_proto.ops[0].op, FillOp)
        assert isinstance(my_proto.ops[1].op, MixOp)
        assert isinstance(my_proto.ops[2].op, ImageOp)

    def test_tracks_well_count(self) -> None:
        @protocol
        def my_proto() -> None:
            list(wells(count=8))

        assert my_proto.well_count == 8

    def test_protocol_repr(self) -> None:
        @protocol
        def my_proto() -> None:
            for well in wells(count=2):
                well.fill(vol=50.0, reagent=red_dye)

        assert "Protocol(ops=2, wells=2)" == repr(my_proto)

    def test_no_trace_leak(self) -> None:
        from biocompute.trace import _current_trace

        @protocol
        def my_proto() -> None:
            list(wells(count=1))

        assert _current_trace.get() is None

    def test_no_trace_leak_on_exception(self) -> None:
        from biocompute.trace import _current_trace

        with pytest.raises(ValueError, match="boom"):

            @protocol
            def my_proto() -> None:
                raise ValueError("boom")

        assert _current_trace.get() is None

    def test_empty_protocol(self) -> None:
        @protocol
        def my_proto() -> None:
            pass

        assert len(my_proto.ops) == 0
        assert my_proto.well_count == 0

    def test_called_directly(self) -> None:
        def my_fn() -> None:
            for well in wells(count=4):
                well.fill(vol=100.0, reagent=red_dye)

        proto = protocol(my_fn)
        assert isinstance(proto, Protocol)
        assert len(proto.ops) == 4


class TestClient:
    """Tests for Client construction and validation."""

    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Client(api_key="sk_test", base_url="")

    def test_rejects_missing_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Client(api_key="sk_test")

    def test_submit_rejects_empty_protocol(self) -> None:
        @protocol
        def empty() -> None:
            pass

        client = Client(api_key="sk_test", base_url="http://localhost:9999")
        with pytest.raises(BiocomputeError, match="no operations"):
            client.submit(empty)
        client.close()

    def test_context_manager(self) -> None:
        with Client(api_key="sk_test", base_url="http://localhost:9999") as client:
            assert client._api_key == "sk_test"
