"""CLI for the London Biocompute competition."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

import click

from biocompute.client import CONFIG_FILE, Client, SubmissionResult, save_config
from biocompute.exceptions import BiocomputeError


def _get_client() -> Client:
    """Create a Client from stored config."""
    try:
        return Client()
    except BiocomputeError:
        click.echo("Not configured. Run `lbc login` first.", err=True)
        sys.exit(1)


@click.group()
def cli() -> None:
    """London Biocompute competition CLI."""


@cli.command()
def login() -> None:
    """Configure API key and server URL."""
    api_key = click.prompt("API key")
    base_url = click.prompt("Server URL", default="https://lbc.fly.dev")

    click.echo("Verifying credentials...")
    try:
        client = Client(api_key=api_key, base_url=base_url)
        user = client.user()
        client.close()
    except BiocomputeError as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(1)

    save_config({"api_key": api_key, "base_url": base_url})
    click.echo(f"Logged in as {user['name']}.")


@cli.command()
def logout() -> None:
    """Remove stored credentials."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        click.echo("Logged out.")
    else:
        click.echo("Not logged in.")



@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--follow", "-f", is_flag=True, help="Follow job progress until completion.")
def submit(file: str, follow: bool) -> None:
    """Submit an experiment file.

    FILE should be a Python file containing an `experiment` function.
    By default, prints the job ID and exits. Use --follow to watch progress.
    """
    path = Path(file).resolve()
    experiment_name = path.stem
    spec = importlib.util.spec_from_file_location("_user_experiment", path)
    if spec is None or spec.loader is None:
        click.echo(f"Cannot load {file}", err=True)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fn = getattr(module, "experiment", None)
    if fn is None:
        click.echo(f"No `experiment` function found in {file}", err=True)
        sys.exit(1)

    client = _get_client()
    try:
        job = client.submit_async(fn)
        job_id = job["id"]

        if not follow:
            name_styled = click.style(experiment_name, fg="blue", bold=True)
            click.echo(f"{name_styled} submitted.")
            click.echo(f"  Experiment ID: {job_id}")
            click.echo(f"  Follow progress: lbc show {job_id} --follow")
            return

        name_styled = click.style(experiment_name, fg="blue", bold=True)
        click.echo(f"Submitted {name_styled}.")

        result = _poll_with_status(client, job_id, experiment_name)

        if result.status == "failed":
            click.echo("")
            click.echo(click.style(f"{experiment_name} failed.", fg="red", bold=True))
            if result.error:
                click.echo(f"  {result.error}")
            sys.exit(1)

    except BiocomputeError as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


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

        data = client.get_experiment(job_id)
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
                results_cmd = click.style(f"lbc show {job_id}", fg="green", bold=True)
                click.echo(f"  {check} {name_styled} completed. View results: {results_cmd}")

            return result

        spinner = click.style(spinner_chars[spinner_idx], fg="cyan")
        label = "Queued" if status == "queued" else "Running"
        click.echo(f"\r  {spinner} {label}...  ", nl=False)
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

        time.sleep(delay)


@cli.command()
def experiments() -> None:
    """List all experiments."""
    client = _get_client()
    try:
        data = client.list_experiments()
        if not data:
            click.echo("No experiments found.")
            return

        rows = [(exp.get("id", "?"), exp.get("status", "unknown")) for exp in data]
        id_width = max(len("Experiment ID"), *(len(r[0]) for r in rows))
        st_width = max(len("Status"), *(len(r[1]) for r in rows))

        header = f"  {'Experiment ID':<{id_width}}  {'Status':<{st_width}}"
        separator = f"  {'─' * id_width}  {'─' * st_width}"
        click.echo(header)
        click.echo(separator)
        for exp_id, status in rows:
            click.echo(f"  {exp_id:<{id_width}}  {status:<{st_width}}")
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


@cli.command()
@click.argument("experiment_id")
@click.option("--follow", "-f", is_flag=True, help="Follow job progress until completion.")
def show(experiment_id: str, follow: bool) -> None:
    """Show details for an experiment."""
    client = _get_client()
    try:
        exp: dict[str, Any] = client.get_experiment(experiment_id)

        if follow:
            status = exp.get("status", "unknown")
            if status in ("complete", "failed"):
                click.echo(f"Job already {status}.")
            else:
                experiment_name = experiment_id[:8]
                _poll_with_status(client, experiment_id, experiment_name)
            return

        for key, value in exp.items():
            click.echo(f"  {key}: {value}")
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
