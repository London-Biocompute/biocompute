# biocompute

Experiment definition and submission library for London Biocompute.

## Install

```bash
pip install biocompute
```

## Usage

Define an experiment function, then submit it with a `Client`:

```python
from biocompute import wells, red_dye, green_dye, blue_dye, Client
import numpy as np

def measure_color(well, r, g, b):
    well.fill(vol=r, reagent=red_dye)
    well.fill(vol=g, reagent=green_dye)
    well.fill(vol=b, reagent=blue_dye)
    well.mix()
    well.image()

n_wells = 25
params = np.linspace([10, 10, 10], [100, 100, 100], num=n_wells)

def my_experiment():
    for well, (r, g, b) in zip(wells(count=n_wells), params):
        measure_color(well, r, g, b)

client = Client(api_key="sk_...", base_url="https://...")
result = client.submit(my_experiment)
```

`wells(count=n)` gives you `n` wells. Pair with any sampling strategy via `zip`.

Use `numpy`, `scipy.stats.qmc`, `pyDOE`, Ax, or any ML model to generate parameter arrays. The system doesn't care — it just sees wells and function calls.

## API

### `Client(api_key, *, challenge_id="default", base_url, timeout=300.0)`

HTTP client for submitting experiments. Optionally use as a context manager:

```python
with Client(api_key="sk_...", base_url="https://...") as client:
    result = client.submit(my_experiment)
```

- `submit(fn)` — run an experiment function, capture its ops, submit, and poll for results
- `target()` — get the target image URL for this challenge
- `leaderboard()` — get the public leaderboard
- `close()` — release resources (called automatically by context manager)

### `wells(count=96)`

Generator that yields `Well` objects. Must be called inside a function passed to `client.submit()`.

### `Well`

- `fill(vol, reagent)` — fill with a volume (microliters) of reagent
- `mix()` — mix well contents
- `image()` — capture an image of the well

All methods return `self` for chaining: `well.fill(vol=50.0, reagent=red_dye).mix().image()`

### Reagents

Built-in: `red_dye`, `green_dye`, `blue_dye`, `water`

Custom: `Reagent("my_reagent")`

## Development

```bash
uv sync              # Install dependencies
uv run pytest        # Run tests
uv run ruff check .  # Lint
uv run mypy .        # Type check
```
