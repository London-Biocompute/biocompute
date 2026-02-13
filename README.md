# biocompute

Python client for the London Biocompute competition. Define experiments as code, submit them via the CLI, and get results back.

## Installation

```bash
pip install biocompute
```

## Quick Start

### 1. Log in

```bash
lbc login
```

You'll be prompted for your API key, server URL, and challenge ID (provided when you enrol). Config is saved to `~/.lbc/config.toml`.

### 2. Write an experiment

Create a file (e.g. `my_experiment.py`) with an `experiment` function:

```python
from biocompute import wells, red_dye, green_dye, blue_dye

def experiment():
    for well in wells(count=3):
        well.fill(vol=80.0, reagent=red_dye)
        well.fill(vol=40.0, reagent=green_dye)
        well.fill(vol=20.0, reagent=blue_dye)
        well.mix()
        well.image()
```

### 3. Submit

```bash
lbc submit my_experiment.py
```

The CLI traces your `experiment` function, sends it to the server, waits for execution on real lab hardware, and prints the result.

### 4. Check results

```bash
lbc experiments          # list all experiments
lbc show <experiment-id> # details for one experiment
lbc leaderboard          # see standings
```

## How It Works

You write a function that describes what should happen in each well of a 96-well microplate. The available operations are:

| Method | Description |
|---|---|
| `well.fill(vol, reagent)` | Dispense `vol` microlitres of `reagent` into the well |
| `well.mix()` | Mix the well contents |
| `well.image()` | Capture an image of the well |

`wells(count=n)` gives you `n` wells. The `experiment` function is traced -- it records every operation and sends them to the server as a batch.

## Available Reagents

Built-in: `red_dye`, `green_dye`, `blue_dye`, `water`

```python
from biocompute import red_dye, green_dye, blue_dye, water
```

## Example: Colour Sweep

Use any Python library to generate parameters. The system just sees wells and operations.

```python
import numpy as np
from biocompute import wells, red_dye, green_dye, blue_dye

def experiment():
    for well, r in zip(wells(count=10), np.linspace(10, 100, 10)):
        well.fill(vol=r, reagent=red_dye)
        well.fill(vol=50.0, reagent=green_dye)
        well.fill(vol=50.0, reagent=blue_dye)
        well.mix()
        well.image()
```

```bash
lbc submit colour_sweep.py
```

## CLI Reference

| Command | Description |
|---|---|
| `lbc login` | Configure API key, server URL, and challenge ID |
| `lbc submit <file.py>` | Submit an experiment file |
| `lbc experiments` | List all experiments with status |
| `lbc show <id>` | Show details for one experiment |
| `lbc leaderboard` | Show challenge standings |

## Python API

You can also use the client library directly:

```python
from biocompute import Client, wells, red_dye

def experiment():
    for well in wells(count=3):
        well.fill(vol=80.0, reagent=red_dye)
        well.mix()
        well.image()

client = Client(api_key="your-api-key", base_url="https://...", challenge_id="...")
result = client.submit(experiment)
print(result.experiment_id)  # unique experiment identifier
print(result.status)         # "complete"
print(result.result_data)    # server response data
```

### `Client(api_key, *, base_url, challenge_id="default", timeout=300.0)`

Create a client. Use as a context manager for automatic cleanup:

```python
with Client(api_key="...", base_url="...") as client:
    result = client.submit(experiment)
```

**Methods:**

- `submit(fn)` -- trace the experiment function, submit it, poll until complete, return a `SubmissionResult`
- `list_experiments()` -- list all experiments
- `get_experiment(experiment_id)` -- get details for one experiment
- `target()` -- get the target image as a base64 string
- `leaderboard()` -- get the current leaderboard

### `SubmissionResult`

Returned by `submit()`:

- `experiment_id` -- unique experiment identifier
- `status` -- `"complete"` or `"failed"`
- `result_data` -- server response data
- `error` -- error message if the experiment failed

## Rules

Each challenge defines constraints. Your experiments must stay within:

- **Allowed reagents** -- only use reagents listed for the challenge
- **Max volume per fill** -- each `fill()` call has a volume cap
- **Max wells per experiment** -- limit on how many wells you can use per submission
- **Wells budget** -- total wells across all submissions is limited
