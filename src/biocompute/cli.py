"""biocompute CLI."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

import click
import httpx

from biocompute.client import (
    CONFIG_FILE,
    DEFAULT_BASE_URL,
    Client,
    SubmissionResult,
    save_config,
)
from biocompute.exceptions import BiocomputeError
from biocompute.visualize import render_cli


def _subscribe(email: str) -> None:
    """Post email to the waitlist endpoint."""
    resp = httpx.post(f"{DEFAULT_BASE_URL}/api/v1/subscribe", json={"email": email, "source": "cli"})
    if resp.status_code in (200, 201):
        click.echo("You're on the list. We'll email you when access is available.")
    elif resp.status_code == 400:
        click.echo("You're already on the list.")
    else:
        click.echo("Something went wrong. Try again later.", err=True)


def _get_client() -> Client:
    """Create a Client from stored config."""
    try:
        return Client()
    except BiocomputeError:
        click.echo("Not logged in.", err=True)
        click.echo("Hardware access is currently limited.", err=True)
        if click.confirm("Want to be notified when access is available?"):
            email = click.prompt("Email")
            _subscribe(email)
        sys.exit(1)


@click.group()
def cli() -> None:
    """biocompute CLI."""


@cli.command()
def login() -> None:
    """Log in with an API key or join the waitlist."""
    click.echo()
    click.echo("[1] Log in with API key")
    click.echo("[2] Join the waitlist")
    click.echo()
    choice = click.prompt("Select", type=click.Choice(["1", "2"]), show_choices=False)

    if choice == "2":
        email = click.prompt("Email")
        _subscribe(email)
        return

    api_key = click.prompt("API key")
    click.echo("Verifying credentials...")
    try:
        client = Client(api_key=api_key, base_url=DEFAULT_BASE_URL)
        user = client.user()
        client.close()
    except BiocomputeError as e:
        click.echo(f"Login failed: {e}", err=True)
        if click.confirm("Want to join the waitlist instead?"):
            email = click.prompt("Email")
            _subscribe(email)
        sys.exit(1)

    save_config({"api_key": api_key, "base_url": DEFAULT_BASE_URL})
    click.echo(f"Logged in as {user['name']}.")


@cli.command()
def logout() -> None:
    """Remove stored credentials."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        click.echo("Logged out.")
    else:
        click.echo("Not logged in.")



def _find_experiments(path: Path) -> list[tuple[str, Any]]:
    """Discover experiment functions in a user script.

    Returns (name, callable) pairs for every top-level function whose name
    starts with ``experiment``, in definition order.
    """
    spec = importlib.util.spec_from_file_location("_user_experiment", path)
    if spec is None or spec.loader is None:
        click.echo(f"Cannot load {path}", err=True)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    experiments: list[tuple[str, Any]] = []
    for name in dir(module):
        if name.startswith("experiment") and callable(getattr(module, name)):
            experiments.append((name, getattr(module, name)))
    # Sort by source line number so order matches the file.
    import inspect

    experiments.sort(key=lambda pair: inspect.getsourcelines(pair[1])[1])
    return experiments


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--follow", "-f", is_flag=True, help="Follow job progress until completion.")
def submit(file: str, follow: bool) -> None:
    """Submit an experiment file.

    FILE should be a Python file containing one or more functions whose names
    start with ``experiment``. Each function is submitted as a separate job.
    """
    path = Path(file).resolve()
    experiments = _find_experiments(path)

    if not experiments:
        click.echo(f"No `experiment` function found in {file}", err=True)
        sys.exit(1)

    client = _get_client()
    failed = False
    try:
        for exp_name, fn in experiments:
            job = client.submit_async(fn)
            job_id = job["id"]

            if not follow:
                name_styled = click.style(exp_name, fg="blue", bold=True)
                click.echo(f"{name_styled} submitted.")
                click.echo(f"  Job ID: {job_id}")
                click.echo(f"  Follow progress: biocompute show {job_id} --follow")
                continue

            name_styled = click.style(exp_name, fg="blue", bold=True)
            click.echo(f"Submitted {name_styled}.")

            result = _poll_with_status(client, job_id, exp_name)

            if result.status == "failed":
                click.echo("")
                click.echo(click.style(f"{exp_name} failed.", fg="red", bold=True))
                if result.error:
                    click.echo(f"  {result.error}")
                failed = True

    except BiocomputeError as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()

    if failed:
        sys.exit(1)


def _poll_with_status(client: Client, job_id: str, experiment_name: str) -> SubmissionResult:
    """Poll for job completion, printing status transitions."""
    delay = 0.15
    last_status = ""
    start = time.monotonic()
    timeout = client._timeout
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    spinner_idx = 0

    status_messages = {
        "queued": "Waiting in queue for an available worker",
        "running": "Experiment is executing on the worker",
    }

    while True:
        elapsed = time.monotonic() - start
        if elapsed > timeout:
            click.echo("")
            raise BiocomputeError(f"Job did not complete within {timeout}s")

        data = client.get_job(job_id)
        status = data.get("status", "unknown")

        if status != last_status:
            if last_status:
                click.echo("\r" + " " * 40 + "\r", nl=False)
            msg = status_messages.get(status, status.capitalize())
            click.echo(f"  {click.style(msg, dim=True)}")
            last_status = status

        if status in ("complete", "failed"):
            click.echo("\r" + " " * 40 + "\r", nl=False)
            result = SubmissionResult.from_job_data(data)

            if status == "complete":
                check = click.style("✔", fg="green", bold=True)
                name_styled = click.style(experiment_name, fg="blue", bold=True)
                results_cmd = click.style(f"biocompute show {job_id}", fg="green", bold=True)
                click.echo(f"  {check} {name_styled} completed. View results: {results_cmd}")
                _print_well_images(result)

            return result

        spinner = click.style(spinner_chars[spinner_idx], fg="cyan")
        label = "Queued" if status == "queued" else "Running"
        click.echo(f"\r  {spinner} {label}...  ", nl=False)
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

        time.sleep(delay)


def _print_well_images(result: SubmissionResult) -> None:
    """Save well images to disk and print their paths."""
    images = result.well_images
    if not images:
        return
    click.echo(f"  Saved {len(images)} well image(s):")
    for well_label, path in sorted(images.items()):
        click.echo(f"    {well_label}: {path}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def visualize(file: str) -> None:
    """Preview experiments without submitting.

    Shows the compiler's execution plan as colored ASCII plates for each
    experiment function in FILE. Runs locally — no server required.
    """
    from biocompute.client import _to_experiments
    from biocompute.trace import collect_trace
    from biocompute.visualize import build_slides_from_experiments

    path = Path(file).resolve()
    experiments = _find_experiments(path)

    if not experiments:
        click.echo(f"No `experiment` function found in {file}", err=True)
        sys.exit(1)

    all_exp_data: list[dict[str, Any]] = []
    for exp_name, fn in experiments:
        trace = collect_trace(fn)
        data = build_slides_from_experiments(_to_experiments(trace.ops))
        all_exp_data.append({"title": exp_name, **data})
    render_cli(all_exp_data)


@cli.command()
def jobs() -> None:
    """List all jobs."""
    client = _get_client()
    try:
        data = client.list_jobs()
        if not data:
            click.echo("No jobs found.")
            return

        rows = [(j.get("id", "?"), j.get("status", "unknown")) for j in data]
        id_width = max(len("Job ID"), *(len(r[0]) for r in rows))
        st_width = max(len("Status"), *(len(r[1]) for r in rows))

        header = f"  {'Job ID':<{id_width}}  {'Status':<{st_width}}"
        separator = f"  {'─' * id_width}  {'─' * st_width}"
        click.echo(header)
        click.echo(separator)
        for job_id, status in rows:
            click.echo(f"  {job_id:<{id_width}}  {status:<{st_width}}")
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


@cli.command()
@click.argument("job_id")
@click.option("--follow", "-f", is_flag=True, help="Follow job progress until completion.")
def show(job_id: str, follow: bool) -> None:
    """Show details for a job."""
    client = _get_client()
    try:
        job: dict[str, Any] = client.get_job(job_id)

        if follow:
            status = job.get("status", "unknown")
            if status in ("complete", "failed"):
                click.echo(f"Job already {status}.")
                if status == "complete":
                    _print_well_images(SubmissionResult.from_job_data(job))
            else:
                job_name = job_id[:8]
                _poll_with_status(client, job_id, job_name)
            return

        for key, value in job.items():
            click.echo(f"  {key}: {value}")

        if job.get("status") == "complete":
            _print_well_images(SubmissionResult.from_job_data(job))
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


@cli.command()
def leaderboard() -> None:
    """Show the challenge leaderboard."""
    client = _get_client()
    try:
        entries = client.leaderboard()
        if not entries:
            click.echo("Leaderboard is empty.")
            return
        for i, entry in enumerate(entries, 1):
            name = entry.get("user_name", "?")
            score = entry.get("best_score", "?")
            click.echo(f"  {i}. {name}  score={score}")
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()
