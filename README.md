# biocompute

London Biocompute client library.

## Install

```bash
pip install biocompute
```

## Usage

```python
from biocompute import Competition, wells, red_dye, green_dye, blue_dye
import numpy as np

with Competition(api_key="sk_...", base_url="https://...") as comp:

    # Experiments are just functions
    def measure_color(well, r, g, b):
        well.fill(vol=r, reagent=red_dye)
        well.fill(vol=g, reagent=green_dye)
        well.fill(vol=b, reagent=blue_dye)
        well.mix()
        well.image()

    # Explore: grid search
    n_wells = 25
    explore = np.linspace([10, 10, 10], [100, 100, 100], num=n_wells)

    for well, (r, g, b) in zip(wells(count=n_wells), explore):
        measure_color(well, r, g, b)

    results = comp.submit()

    # Find best well
    best_idx = max(range(len(results.wells)), key=lambda i: results.wells[i].score or 0)
    best_params = explore[best_idx]

with Competition(api_key="sk_...", base_url="https://...") as comp:

    # Exploit: random samples around best hit
    exploit = np.random.normal(best_params, scale=5, size=(n_wells, 3)).clip(0, 200)

    for well, (r, g, b) in zip(wells(count=n_wells), exploit):
        measure_color(well, r, g, b)

    results = comp.submit()
```

`wells(count=n)` gives you `n` wells. Pair with any sampling strategy via `zip`.

Use `numpy`, `scipy.stats.qmc`, `pyDOE`, Ax, or any ML model to generate parameter arrays. The system doesn't care — it just sees wells and function calls.

## API

### `Competition(api_key, *, challenge_id="default", base_url, timeout=300.0)`

Creates a competition session. Use as a context manager to ensure cleanup.

- `submit()` — serialize recorded ops, POST to server, poll for results
- `target()` — get the target image URL for this challenge
- `leaderboard()` — get the public leaderboard
- `close()` — release resources (called automatically by context manager)

### `wells(count=96)`

Generator that yields `Well` objects. Must be called after creating a `Competition`.

### `Well`

- `fill(vol, reagent)` — fill with a volume (microliters) of reagent
- `mix()` — mix well contents
- `image()` — capture an image of the well

All methods return `self` for chaining: `well.fill(vol=50.0, reagent=red_dye).mix().image()`

### Reagents

Built-in: `red_dye`, `green_dye`, `blue_dye`, `water`

Custom: `Reagent("my_reagent")`

## Build & Publish

```bash
cd biocompute

# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Lint & type check
uv run ruff check .
uv run mypy src/biocompute

# Build (leakage check runs automatically)
uv run python -m build

# Manual leakage check
python check_leakage.py
```

The build includes an automatic leakage check (`hatch_build.py`) that scans for references to private internal modules and aborts if any are found.
