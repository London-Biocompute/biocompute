"""Leakage detection for the biocompute package.

Scans source files for references to private internal modules
(controller.*, compiler types, hardware details) that should
never ship in the public package.

Used by:
- hatch_build.py (build hook, runs automatically on build)
- check_leakage.py (CLI, for manual checks)
"""

from __future__ import annotations

import re
from pathlib import Path

# Patterns that indicate leakage of private internals
FORBIDDEN = [
    (r"\bfrom\s+controller\b", "import from controller (private)"),
    (r"\bimport\s+controller\b", "import of controller (private)"),
    (r"\bUOp\b", "reference to internal UOp type"),
    (r"\bSourceLocation\b", "reference to internal SourceLocation"),
    (r"\bcompile_protocol\b", "reference to compile_protocol"),
    (r"\bCodeGenerator\b", "reference to internal CodeGenerator"),
    (r"\bDependencyDAG\b", "reference to internal DependencyDAG"),
    (r"\bAssignmentPlan\b", "reference to internal AssignmentPlan"),
    (r"\bWorkcellSpec\b", "reference to internal WorkcellSpec"),
    (r"\bDeviceSpec\b", "reference to internal DeviceSpec"),
    (r"sk_[a-zA-Z0-9]{20,}", "possible API key literal"),
    (r"/Users/\w+/", "absolute local path"),
]

SKIP_FILES = {"check_leakage.py", "conftest.py", "_leakage.py", "hatch_build.py"}


def scan_file(path: Path, relative_to: Path | None = None) -> list[str]:
    """Scan a single Python file for forbidden patterns.

    Returns a list of human-readable hit descriptions.
    """
    if path.name in SKIP_FILES:
        return []
    text = path.read_text()
    hits: list[str] = []
    display = str(path.relative_to(relative_to)) if relative_to else str(path)
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern, reason in FORBIDDEN:
            if re.search(pattern, line):
                hits.append(f"  {display}:{lineno}: {reason}\n    {line.strip()}")
    return hits


def scan_source(src_dir: Path, relative_to: Path | None = None) -> list[str]:
    """Scan all Python files under a directory."""
    hits: list[str] = []
    for py in sorted(src_dir.rglob("*.py")):
        hits.extend(scan_file(py, relative_to=relative_to))
    return hits
