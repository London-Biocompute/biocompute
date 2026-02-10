# biocompute

Protocol definition and submission library for London Biocompute.

## Install

```bash
pip install biocompute
```

## Usage

Define a protocol with the `@protocol` decorator, then submit it with a `Client`:

```python
from biocompute import protocol, wells, red_dye, green_dye, blue_dye, Client
import numpy as np

def measure_color(well, r, g, b):
    well.fill(vol=r, reagent=red_dye)
    well.fill(vol=g, reagent=green_dye)
    well.fill(vol=b, reagent=blue_dye)
    well.mix()
    well.image()

# Explore: grid search
n_wells = 25
explore = np.linspace([10, 10, 10], [100, 100, 100], num=n_wells)

@protocol
def explore_protocol():
    for well, (r, g, b) in zip(wells(count=n_wells), explore):
        measure_color(well, r, g, b)

client = Client(api_key="sk_...", base_url="https://...")
results = client.submit(explore_protocol)

# Find best well
best_idx = max(range(len(results.wells)), key=lambda i: results.wells[i].score or 0)
best_params = explore[best_idx]

# Exploit: random samples around best hit
exploit = np.random.normal(best_params, scale=5, size=(n_wells, 3)).clip(0, 200)

@protocol
def exploit_protocol():
    for well, (r, g, b) in zip(wells(count=n_wells), exploit):
        measure_color(well, r, g, b)

results = client.submit(exploit_protocol)
```

`wells(count=n)` gives you `n` wells. Pair with any sampling strategy via `zip`.

Use `numpy`, `scipy.stats.qmc`, `pyDOE`, Ax, or any ML model to generate parameter arrays. The system doesn't care — it just sees wells and function calls.

## API

### `@protocol`

Decorator that captures well operations into a `Protocol` object:

```python
@protocol
def my_experiment():
    for well in wells(count=96):
        well.fill(100.0, water)

my_experiment.ops         # list of TracedOp
my_experiment.well_count  # 96
```

Can also be called directly: `proto = protocol(some_function)`

### `Client(api_key, *, challenge_id="default", base_url, timeout=300.0)`

HTTP client for submitting protocols. Optionally use as a context manager:

```python
with Client(api_key="sk_...", base_url="https://...") as client:
    result = client.submit(my_protocol)
```

- `submit(proto)` — submit a `Protocol`, poll for results
- `target()` — get the target image URL for this challenge
- `leaderboard()` — get the public leaderboard
- `close()` — release resources (called automatically by context manager)

### `wells(count=96)`

Generator that yields `Well` objects. Must be called inside a `@protocol` function.

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
