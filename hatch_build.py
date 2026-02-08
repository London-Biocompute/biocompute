"""Hatchling build hook that runs leakage detection before building.

Automatically invoked by hatchling during `python -m build` or
`hatch build`. Aborts the build if any private internal references
are found in the source.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Load _leakage.py directly to avoid importing the full biocompute
# package (which requires httpx, not available in the build env).
_leakage_path = Path(__file__).parent / "_leakage.py"
_spec = importlib.util.spec_from_file_location("_leakage", _leakage_path)
assert _spec is not None and _spec.loader is not None
_leakage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_leakage)


class LeakageCheckHook(BuildHookInterface):
    PLUGIN_NAME = "leakage-check"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        src = Path(__file__).parent / "src" / "biocompute"
        hits: list[str] = _leakage.scan_source(src, relative_to=Path(__file__).parent)  # type: ignore[attr-defined]

        if hits:
            msg = f"Leakage check FAILED — {len(hits)} issue(s) found:\n" + "\n".join(hits)
            raise RuntimeError(msg)
