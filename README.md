<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo_dark.svg">
  <img alt="biocompute" src="assets/logo_light.svg" width="40%">
</picture>

<br>

Wet lab automation as Python code. Maintained by [london biocompute](https://londonbiocompute.com).

</div>

---

**biocompute** is a framework that lets you write wet lab experiments as plain Python. Every `well.fill()`, `well.mix()`, `well.image()` call is traced locally and sent as a batch to real lab hardware. No drag-and-drop GUIs, no vendor lock-in, no manual pipetting.

If you know Python, you already know how to run wet lab experiments.

---

## Quick start

```bash
pip install biocompute
lbc login
```

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

```bash
lbc submit my_experiment.py --follow
```

And that's it. Results stream back to your terminal.

---

## How it works

You write a function, then submit. The compiler figures out what equipment is needed, optimises the layout, and runs it faster than any manually-configured setup could.

```
  Write Python  →  Submit to server  →  Compile experiment  →  Execute on hardware
```

### Operations

| Method | What it does |
| --- | --- |
| `well.fill(vol, reagent)` | Dispense `vol` µL of `reagent` |
| `well.mix()` | Mix well contents |
| `well.image()` | Capture an image |

`wells(count=n)` yields `n` wells. Multiple calls produce non-overlapping wells.

### Reagents

```python
from biocompute import red_dye, green_dye, blue_dye, water
```

---

## Because it's just Python

Use numpy. Use scipy. Use whatever. The system only sees wells and operations.

### Colour sweep

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
