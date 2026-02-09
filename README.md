# biocompute

London Biocompute client library.

## Install

```bash
pip install biocompute
```

## Usage

```python
from biocompute import Client, Well, Dye
import numpy as np

client = Client(api_key="sk_...", base_url="https://...")

# Get the target image
target_b64 = client.get_target("challenge-id")

# Experiments are just functions
def measure_color(r, g, b):
    return (
        Well()
        .fill(Dye.RED, r)
        .fill(Dye.GREEN, g)
        .fill(Dye.BLUE, b)
        .mix()
        .image()
    )

# Explore: grid search
params = np.linspace([10, 10, 10], [100, 100, 100], num=25)
wells = [measure_color(r, g, b) for r, g, b in params]
result = client.submit("challenge-id", wells)

# Check leaderboard
for entry in client.leaderboard("challenge-id"):
    print(f"#{entry.rank} {entry.user_name}: {entry.best_score}")

```

`Well()` records operations. `Client.submit()` sends them all in one request. Pair with any sampling strategy — `numpy`, `scipy`, Ax, or any ML model.

## API

### `Client(api_key, base_url, timeout=300.0)`

Client for submitting jobs and retrieving results.

- `submit(challenge_id, wells)` — submit wells, poll for results, return `SubmissionResult`
- `get_target(challenge_id)` — get the base64-encoded target image
- `leaderboard(challenge_id)` — get `list[LeaderboardEntry]`

### `Well()`

Records operations. Takes no arguments.

- `fill(dye, volume)` — fill with a dye (microliters)
- `mix()` — mix well contents
- `image()` — capture an image of the well

All methods return `self` for chaining: `Well().fill(Dye.RED, 50.0).mix().image()`

### `Dye`

Enum of available dyes: `Dye.RED`, `Dye.GREEN`, `Dye.BLUE`

### `SubmissionResult`

Returned by `client.submit()`. Fields: `id`, `challenge_id`, `status`, `wells_count`, `result_data`, `error_message`, `raw`.

### `LeaderboardEntry`

Returned by `client.leaderboard()`. Fields: `rank`, `user_name`, `wells_consumed`, `best_score`, `raw`.
