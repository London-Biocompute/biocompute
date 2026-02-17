"""CLI plate visualization — renders slides as colored ASCII in the terminal.

Also contains :func:`build_slides_from_experiments`, a self-contained
pipeline that converts serialised experiments into slide JSON without
depending on the ``controller`` package.
"""

from __future__ import annotations

import colorsys
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

ROWS = "ABCDEFGH"
COLS = 12
WELLS_PER_PLATE = 96

# ── Reagent colours ──────────────────────────────────────────────

_COLORS: dict[str, str] = {
    "red_dye": "#e74c3c",
    "green_dye": "#2ecc71",
    "blue_dye": "#3498db",
    "yellow_dye": "#f1c40f",
    "water": "#d4e6f1",
    "pbs": "#c8dce6",
    "dmso": "#dcd0ff",
    "media": "#ffe0b2",
    "serum": "#fff3cd",
    "trypsin": "#e8f5e9",
}


def _reagent_color(name: str) -> str:
    if name in _COLORS:
        return _COLORS[name]
    h = (hash(name) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(h, 0.6, 0.7)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _blend_colors(fills: list[tuple[str, float]]) -> str:
    if not fills:
        return "#f0f0f0"
    total = sum(v for _, v in fills)
    if total == 0:
        return "#f0f0f0"
    r = g = b = 0.0
    for name, vol in fills:
        c = _reagent_color(name)
        r += int(c[1:3], 16) * vol / total
        g += int(c[3:5], 16) * vol / total
        b += int(c[5:7], 16) * vol / total
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


# ── Well helpers ─────────────────────────────────────────────────


def _well_label(well_idx: int) -> tuple[int, str]:
    """Return (plate_id, 'A1'-style label) for an abstract well index."""
    plate_id = well_idx // WELLS_PER_PLATE
    plate_well = well_idx % WELLS_PER_PLATE
    row = plate_well // 12
    col = plate_well % 12
    return plate_id, f"{chr(65 + row)}{col + 1}"


def _sort_well_labels(labels: list[str]) -> list[str]:
    def key(label: str) -> tuple[str, int]:
        m = re.match(r"([A-H])(\d+)", label)
        return (m.group(1), int(m.group(2))) if m else (label, 0)

    return sorted(labels, key=key)


def _format_wells(labels: list[str]) -> str:
    labels = _sort_well_labels(labels)
    if len(labels) <= 3:
        return ", ".join(labels)
    return f"{labels[0]}\u2013{labels[-1]}"


@dataclass
class _WellState:
    fills: list[tuple[str, float]] = field(default_factory=list)
    mixed: bool = False

    @property
    def volume(self) -> float:
        return sum(v for _, v in self.fills)

    @property
    def color(self) -> str:
        return _blend_colors(self.fills)

    def to_dict(self) -> dict[str, Any]:
        return {
            "color": self.color,
            "volume_ul": self.volume,
            "mixed": self.mixed,
            "fills": [{"reagent": n, "volume_ul": v} for n, v in self.fills],
        }


# ── Slide builder ────────────────────────────────────────────────


def _batch_title(batch: list[dict[str, Any]]) -> str:
    """Human-readable title for a batch of ops."""
    fills: list[dict[str, Any]] = []
    mixes: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    for op in batch:
        kind = op["op"]
        if kind == "fill":
            fills.append(op)
        elif kind == "mix":
            mixes.append(op)
        elif kind == "image":
            images.append(op)

    parts: list[str] = []
    if fills:
        by_reagent: dict[str, tuple[list[str], float]] = {}
        for f in fills:
            _, label = _well_label(f["well_idx"])
            reagent = f["reagent"]
            if reagent not in by_reagent:
                by_reagent[reagent] = ([], f["volume"])
            by_reagent[reagent][0].append(label)
        for reagent, (labels, vol) in by_reagent.items():
            parts.append(f"Fill {_format_wells(labels)} with {reagent} ({vol} \u00b5L)")
    if mixes:
        labels = sorted({_well_label(m["well_idx"])[1] for m in mixes})
        parts.append(f"Mix {_format_wells(labels)}")
    if images:
        labels = sorted({_well_label(i["well_idx"])[1] for i in images})
        parts.append(f"Image {_format_wells(labels)}")

    return "; ".join(parts) if parts else "No-op"


def build_slides_from_experiments(
    experiments: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build visualisation slide data from serialised experiments.

    Self-contained pipeline for fill/mix/image ops — does not
    depend on the ``controller`` compiler.

    Each experiment is one well.  Ops within a well are sequential;
    ops across wells at the same position form a parallelisable batch
    (i.e. the i-th op of every well becomes batch *i*).

    Returns dict with ``slides`` and ``reagent_legend`` keys, matching
    the format expected by :func:`render_cli`.
    """
    # Flatten experiments into per-well op lists annotated with well_idx.
    per_well: dict[int, list[dict[str, Any]]] = {}
    for well_idx, ops in enumerate(experiments):
        annotated: list[dict[str, Any]] = []
        for uop in ops:
            annotated.append({**uop, "well_idx": well_idx})
        per_well[well_idx] = annotated

    # Build batches: batch i = the i-th op from each well.
    max_ops = max((len(ops) for ops in per_well.values()), default=0)
    batches: list[list[dict[str, Any]]] = []
    for i in range(max_ops):
        batch: list[dict[str, Any]] = []
        for well_idx in sorted(per_well):
            ops = per_well[well_idx]
            if i < len(ops):
                batch.append(ops[i])
        batches.append(batch)

    # Walk batches, accumulating well state and producing slides.
    well_states: dict[tuple[int, str], _WellState] = {}
    reagents_used: set[str] = set()
    slides: list[dict[str, Any]] = []

    for batch in batches:
        for op in batch:
            kind = op["op"]
            pid, label = _well_label(op["well_idx"])
            key = (pid, label)
            if key not in well_states:
                well_states[key] = _WellState()

            if kind == "fill":
                well_states[key].fills.append((op["reagent"], op["volume"]))
                reagents_used.add(op["reagent"])
            elif kind == "mix":
                well_states[key].mixed = True

        # Snapshot: group by plate.
        plates_data: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        for (pid, label), ws in sorted(well_states.items()):
            plates_data[pid][label] = ws.to_dict()

        plate_list = [
            {"label": f"Plate {pid + 1}", "wells": wells}
            for pid, wells in sorted(plates_data.items())
        ]

        slides.append({
            "title": _batch_title(batch),
            "plates": plate_list,
        })

    legend = {name: _reagent_color(name) for name in sorted(reagents_used)}
    return {"slides": slides, "reagent_legend": legend}


# ── Well cell rendering ───────────────────────────────────────────

_WELL_FILLED = "\u25cf"  # ● filled circle
_WELL_MIXED = "\u21bb"  # ↻ clockwise arrow (swirl)
_WELL_EMPTY = "\u25cb"  # ○ empty circle


def _well_cell(w: dict[str, Any] | None) -> Any:
    """Return a Rich Text for a single well cell."""
    from rich.style import Style
    from rich.text import Text

    if w:
        color = w.get("color", "#f0f0f0")
        char = _WELL_MIXED if w.get("mixed") else _WELL_FILLED
        return Text(f" {char}", style=Style(color=color))
    return Text(f" {_WELL_EMPTY}", style="dim")


def _build_plate_table(plate: dict[str, Any]) -> Any:
    """Build a Rich Table for one 8x12 plate with circular well characters."""
    from rich.table import Table
    from rich.text import Text

    table = Table(show_header=True, show_edge=False, pad_edge=False, box=None, padding=(0, 1))
    table.add_column("", style="dim", width=1)
    for c in range(1, COLS + 1):
        table.add_column(str(c), justify="center", width=2)

    wells: dict[str, Any] = plate.get("wells", {})
    for r_idx in range(8):
        rl = ROWS[r_idx]
        cells: list[Text] = [Text(rl, style="dim")]
        for c in range(1, COLS + 1):
            cells.append(_well_cell(wells.get(f"{rl}{c}")))
        table.add_row(*cells)
    return table


def _build_legend_text(legend: dict[str, str]) -> Any:
    from rich.style import Style
    from rich.text import Text

    text = Text()
    for i, (name, color) in enumerate(legend.items()):
        if i > 0:
            text.append("  ")
        text.append(f" {_WELL_FILLED}", style=Style(color=color))
        text.append(f" {name}")
    return text


# ── Plain-text fallback (non-TTY / piped output) ─────────────────


def _render_all(
    slides: list[dict[str, Any]],
    legend: dict[str, str],
    title: str = "",
) -> None:
    """Non-interactive: print all slides sequentially using Rich tables."""
    from rich.console import Console
    from rich.text import Text

    console = Console()

    if title:
        heading = Text(f"\n  {title}", style="bold underline")
        console.print(heading)
        console.print()

    for idx, slide in enumerate(slides):
        step_title = slide.get("title", "")
        header = Text()
        header.append(f"Step {idx + 1} of {len(slides)}", style="dim")
        header.append("  ")
        header.append(step_title, style="bold")
        console.print(header)
        console.print()

        for pi, plate in enumerate(slide.get("plates", [])):
            label = plate.get("label", f"Plate {pi + 1}")
            console.print(f"  [dim]{label}[/dim]")
            console.print(_build_plate_table(plate))
            console.print()

        console.print(_build_legend_text(legend))
        console.print()


# ── Textual TUI (interactive mode) ───────────────────────────────


def _run_textual_app(
    slides: list[dict[str, Any]],
    legend: dict[str, str],
    title: str = "",
) -> None:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Footer, Static

    class SlideViewerApp(App[None]):
        CSS = """
        Screen {
            layout: vertical;
        }
        #experiment-name {
            margin: 1 2 0 2;
            text-style: bold underline;
        }
        #step-counter {
            margin: 1 2 0 2;
            color: $text-muted;
        }
        #step-title {
            margin: 0 2 1 2;
            text-style: bold;
        }
        #legend {
            margin: 1 2;
        }
        """

        BINDINGS = [
            Binding("right", "next_slide", "Next"),
            Binding("left", "prev_slide", "Previous"),
            Binding("q", "quit", "Quit"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._current = 0
            self._slides = slides
            self._legend = legend
            self._title = title

        def compose(self) -> ComposeResult:
            yield Static(self._title, id="experiment-name")
            yield Static("", id="step-counter")
            yield Static("", id="step-title")
            yield Static("", id="plates-container")
            yield Static("", id="legend")
            yield Footer()

        def on_mount(self) -> None:
            self._refresh_slide()

        def _refresh_slide(self) -> None:
            slide = self._slides[self._current]
            total = len(self._slides)
            step_title = slide.get("title", "")

            self.query_one("#step-counter", Static).update(
                f"Step {self._current + 1} of {total}"
            )
            self.query_one("#step-title", Static).update(step_title)

            from rich.console import Group, RenderableType
            from rich.text import Text

            parts: list[RenderableType] = []
            for pi, plate in enumerate(slide.get("plates", [])):
                label = plate.get("label", f"Plate {pi + 1}")
                parts.append(Text(label, style="dim"))
                parts.append(_build_plate_table(plate))
                parts.append(Text(""))

            self.query_one("#plates-container", Static).update(Group(*parts))
            self.query_one("#legend", Static).update(_build_legend_text(self._legend))

        def action_next_slide(self) -> None:
            if self._current < len(self._slides) - 1:
                self._current += 1
                self._refresh_slide()

        def action_prev_slide(self) -> None:
            if self._current > 0:
                self._current -= 1
                self._refresh_slide()

    SlideViewerApp().run()


# ── Public entry point ────────────────────────────────────────────


def render_cli(data: dict[str, Any], *, title: str = "") -> None:
    """Render slides interactively in the terminal.

    Arrow keys to navigate, 'q' to quit.
    Falls back to non-interactive plain-text mode if not a TTY.
    """
    slides = data.get("slides", [])
    legend = data.get("reagent_legend", {})

    if not slides:
        print("No slides to display.")
        return

    if not sys.stdin.isatty():
        _render_all(slides, legend, title=title)
        return

    _run_textual_app(slides, legend, title=title)
