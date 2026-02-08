#!/usr/bin/env python3
"""Manual leakage check CLI.

The same check runs automatically during `hatch build` / `python -m build`
via the build hook in hatch_build.py. This script is for quick manual runs.

Usage:
    python check_leakage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Import from project root (not shipped inside the package)
sys.path.insert(0, str(Path(__file__).parent))

from _leakage import scan_source  # noqa: E402

ROOT = Path(__file__).parent
SRC = ROOT / "src" / "biocompute"


def main() -> int:
    print("Scanning source files...")
    hits = scan_source(SRC, relative_to=ROOT)
    if hits:
        print(f"\nFOUND {len(hits)} leakage(s):\n")
        print("\n".join(hits))
        print("\nFAILED: Fix leakage before publishing.")
        return 1
    print("PASSED: No leakage detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
