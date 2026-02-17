<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo_dark.svg">
  <img alt="biocompute" src="assets/logo_light.svg" width="50%">
</picture>

<br>

Wet lab automation as Python code. Maintained by [london biocompute](https://londonbiocompute.com).

</div>

[![PyPI version](https://img.shields.io/pypi/v/biocompute)](https://pypi.org/project/biocompute/)
[![Python](https://img.shields.io/pypi/pyversions/biocompute)](https://pypi.org/project/biocompute/)
[![License](https://img.shields.io/github/license/bjsi/biocompute)](LICENSE)

**biocompute** is a framework that lets you write wet lab experiments as plain Python. Define your protocol with calls like `well.fill()`, `well.mix()`, and `well.image()`. Then execute on real lab hardware that handles the liquid dispensing, mixing, and imaging automatically. No drag-and-drop GUIs, no vendor lock-in, no manual pipetting.

If you know Python, you can run wet lab experiments.

---

## Quick start

Create a virtual environment and install the `biocompute` package.

```bash
python -m venv .venv
source .venv/bin/activate
pip install biocompute
```

Create a file called `super_simple_experiment.py` and copy the code snippet.

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

Submit the experiment to the job server.

```bash
lbc submit super_simple_experiment.py --follow
```

And that's it. Results stream back to your terminal as experiments finish executing on the physical hardware.

---

## How it works

Your experiment function describes intent. The compiler takes this high-level declarative code and turns it into a fully scheduled, hardware-specific protocol. It handles:

- **Automatic parallelism** — independent operations are identified and scheduled concurrently so protocols finish faster without any manual orchestration.
- **Plate layout** — wells are assigned to physical plates based on thermal constraints. Multi-temperature experiments get split across plates automatically.
- **Operation collapsing** — redundant per-well instructions (like 96 identical incubations) are collapsed into single plate-level commands.
- **Device mapping** — every operation is matched to the right piece of hardware (pipette, camera, incubator, gripper) based on a capability model, so swapping equipment never means rewriting your protocol.
- **Multi-plate scaling** — protocols that exceed a single plate are transparently distributed across as many plates as needed.

You describe what should happen. The compiler figures out how to make it fast.

### Operations

| Method | What it does |
| --- | --- |
| `well.fill(vol, reagent)` | Dispense `vol` µL of `reagent` |
| `well.mix()` | Mix well contents |
| `well.image()` | Capture an image |

`wells(count=n)` yields `n` wells. Multiple calls produce non-overlapping wells.

### Reagents

Import the built-in reagents you need.

```python
from biocompute import red_dye, green_dye, blue_dye, water
```

---

## Because it's just Python

Use numpy. Use scipy. Use whatever. The system only sees wells and operations.

### Colour sweep

Sweep red dye volume across ten wells using numpy to generate the range.

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

### Closed-loop optimisation

Submit an experiment, read results, use them to parameterise the next one.

```python
import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import minimize_scalar
from biocompute import Client, wells, red_dye, green_dye

with Client() as client:
    volumes = np.linspace(10, 100, 8)

    def experiment_sweep():
        for well, v in zip(wells(count=8), volumes):
            well.fill(vol=v, reagent=red_dye)
            well.fill(vol=50.0, reagent=green_dye)
            well.mix()
            well.image()

    result = client.submit(experiment_sweep)

    model = interp1d(volumes, result.result_data["scores"], kind="cubic")
    optimum = minimize_scalar(model, bounds=(10, 100), method="bounded").x

    def experiment_refine():
        for well, v in zip(wells(count=5), np.linspace(optimum - 10, optimum + 10, 5)):
            well.fill(vol=v, reagent=red_dye)
            well.fill(vol=50.0, reagent=green_dye)
            well.mix()
            well.image()

    final = client.submit(experiment_refine)
```
