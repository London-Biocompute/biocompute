```
             _                 _
            | | ___  _ __   __| | ___  _ __
            | |/ _ \| '_ \ / _` |/ _ \| '_ \
            | | (_) | | | | (_| | (_) | | | |
            |_|\___/|_| |_|\__,_|\___/|_| |_|

  _     _                                     _
 | |__ (_) ___   ___ ___  _ __ ___  _ __  _  _| |_ ___
 | '_ \| |/ _ \ / __/ _ \| '_ ` _ \| '_ \| | | | __/ _ \
 | |_) | | (_) | (_| (_) | | | | | | |_) | |_| | ||  __/
 |_.__/|_|\___/ \___\___/|_| |_| |_| .__/ \__,_|\__\___|
                                    |_|
```

**Define experiments as Python code. Run them on real lab hardware.**

Python client for [London Biocompute](https://londonbiocompute.com). Write functions that describe microplate operations, submit them from your terminal, and get results back from automated lab equipment.

---

## Installation

```bash
pip install biocompute
```

Requires Python 3.10+.

## Quick Start

```bash
lbc login
```

```python
# my_experiment.py
from biocompute import wells, red_dye, green_dye, blue_dye

def experiment():
    for well in wells(count=3):
        well.fill(vol=80.0, reagent=red_dye)
        well.fill(vol=40.0, reagent=green_dye)
        well.fill(vol=20.0, reagent=blue_dye)
        well.mix()
        well.image()
```

```bash
lbc submit my_experiment.py --follow
```

## How It Works

You describe what should happen in each well of a 96-well microplate. The `experiment` function is traced - every operation is recorded and sent to the server as a batch.

```
  +-----------+     +-----------+     +-----------+     +-----------+
  |  Write    | --> |  Trace    | --> |  Submit   | --> |  Execute  |
  |  Python   |     |  ops      |     |  to       |     |  on real  |
  |  code     |     |  locally  |     |  server   |     |  hardware |
  +-----------+     +-----------+     +-----------+     +-----------+
```

### Well operations

| Method                    | Description                                    |
| ------------------------- | ---------------------------------------------- |
| `well.fill(vol, reagent)` | Dispense `vol` microlitres of `reagent`        |
| `well.mix()`              | Mix the well contents                          |
| `well.image()`            | Capture an image of the well                   |

`wells(count=n)` yields `n` wells with auto-incrementing indices. Multiple calls within the same experiment produce non-overlapping wells.

### Available reagents

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

## Example: Closed-Loop Optimisation

Because experiments are just Python, you can run a closed loop from a single script - submit an experiment, read the results, and use them to parameterise the next one.

```python
import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import minimize_scalar
from biocompute import Client, wells, red_dye, green_dye

with Client() as client:
    # Experiment 1: sweep red dye volumes
    volumes = np.linspace(10, 100, 8)

    def experiment_sweep():
        for well, v in zip(wells(count=8), volumes):
            well.fill(vol=v, reagent=red_dye)
            well.fill(vol=50.0, reagent=green_dye)
            well.mix()
            well.image()

    result = client.submit(experiment_sweep)

    # Fit a curve to the scores and find the minimum
    model = interp1d(volumes, result.result_data["scores"], kind="cubic")
    optimum = minimize_scalar(model, bounds=(10, 100), method="bounded").x

    # Experiment 2: refine around the optimum
    def experiment_refine():
        for well, v in zip(wells(count=5), np.linspace(optimum - 10, optimum + 10, 5)):
            well.fill(vol=v, reagent=red_dye)
            well.fill(vol=50.0, reagent=green_dye)
            well.mix()
            well.image()

    final = client.submit(experiment_refine)
```

## License

MIT
