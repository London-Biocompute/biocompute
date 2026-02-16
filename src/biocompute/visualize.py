"""CLI plate visualization — renders slides as colored ASCII in the terminal."""

from __future__ import annotations

import sys
from typing import Any

ROWS = "ABCDEFGH"
COLS = 12


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _fg(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


def _bg(r: int, g: int, b: int) -> str:
    return f"\033[48;2;{r};{g};{b}m"


_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _render_plate(plate: dict[str, Any]) -> list[str]:
    """Render a single plate as background-colored blocks."""
    wells = plate.get("wells", {})
    lines: list[str] = []

    # Column headers — 3 chars per cell: 2 for block + 1 gap
    hdr = "     "
    for c in range(1, COLS + 1):
        hdr += f"{c:>2} "
    lines.append(f"{_DIM}{hdr}{_RESET}")

    for r in range(8):
        rl = ROWS[r]
        row = f"  {_DIM}{rl}{_RESET}  "
        for c in range(1, COLS + 1):
            label = f"{rl}{c}"
            w = wells.get(label)
            if w:
                rgb = _hex_to_rgb(w.get("color", "#f0f0f0"))
                if w.get("mixed"):
                    row += f"{_bg(*rgb)}{_fg(255, 255, 255)}\u2248 {_RESET} "
                else:
                    row += f"{_bg(*rgb)}  {_RESET} "
            else:
                row += f"{_DIM}\u00b7\u00b7{_RESET} "
        lines.append(row)

    return lines


def _render_legend(legend: dict[str, str]) -> str:
    """Render reagent legend as colored blocks."""
    parts: list[str] = []
    for name, color in legend.items():
        rgb = _hex_to_rgb(color)
        parts.append(f"{_bg(*rgb)}  {_RESET} {name}")
    return "  ".join(parts)


def _render_all(slides: list[dict[str, Any]], legend: dict[str, str]) -> None:
    """Non-interactive: print all slides sequentially."""
    for i, slide in enumerate(slides):
        _print_slide(i, slide, len(slides), legend)
        print()


def _print_slide(
    idx: int,
    slide: dict[str, Any],
    total: int,
    legend: dict[str, str],
) -> None:
    """Print a single slide to stdout."""
    title = slide.get("title", "")
    print(f"{_DIM}Step {idx + 1} of {total}{_RESET}  {_BOLD}{title}{_RESET}")
    print()

    for pi, plate in enumerate(slide.get("plates", [])):
        label = plate.get("label", f"Plate {pi + 1}")
        print(f"  {_DIM}{label}{_RESET}")
        for line in _render_plate(plate):
            print(f"  {line}")
        print()

    print(f"  {_render_legend(legend)}")


def _render_interactive(slides: list[dict[str, Any]], legend: dict[str, str]) -> None:
    """Interactive mode: navigate with keyboard."""
    import tty
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    current = 0

    def draw() -> None:
        sys.stdout.write("\033[2J\033[H")
        _print_slide(current, slides[current], len(slides), legend)
        print()
        print(f"{_DIM}\u2190/\u2192 or enter to navigate, q to quit{_RESET}")
        sys.stdout.flush()

    try:
        tty.setraw(fd)
        draw()

        while True:
            ch = sys.stdin.read(1)
            if ch == "q" or ch == "\x03":
                break
            elif ch == "\r" or ch == " " or ch == "n":
                if current < len(slides) - 1:
                    current += 1
                    draw()
            elif ch == "p" or ch == "b":
                if current > 0:
                    current -= 1
                    draw()
            elif ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[C":
                    if current < len(slides) - 1:
                        current += 1
                        draw()
                elif seq == "[D":
                    if current > 0:
                        current -= 1
                        draw()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def render_cli(data: dict[str, Any]) -> None:
    """Render slides interactively in the terminal.

    Arrow keys or enter to advance, 'q' to quit.
    Falls back to non-interactive mode if not a TTY.
    """
    slides = data.get("slides", [])
    legend = data.get("reagent_legend", {})

    if not slides:
        print("No slides to display.")
        return

    if not sys.stdin.isatty():
        _render_all(slides, legend)
        return

    _render_interactive(slides, legend)
