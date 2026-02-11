"""Tests for the Client API."""

from __future__ import annotations

import pytest

from biocompute.client import Client
from biocompute.exceptions import BiocomputeError
from biocompute.well import wells


class TestClient:
    """Tests for Client construction and validation."""

    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Client(api_key="sk_test", base_url="")

    def test_rejects_missing_base_url(self) -> None:
        with pytest.raises(BiocomputeError, match="base_url is required"):
            Client(api_key="sk_test")

    def test_submit_rejects_empty_experiment(self) -> None:
        def empty() -> None:
            pass

        client = Client(api_key="sk_test", base_url="http://localhost:9999")
        with pytest.raises(BiocomputeError, match="no operations"):
            client.submit(empty)
        client.close()

    def test_context_manager(self) -> None:
        with Client(api_key="sk_test", base_url="http://localhost:9999") as client:
            assert client._api_key == "sk_test"
