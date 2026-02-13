"""CLI for the London Biocompute competition."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import click

from biocompute.client import _CONFIG_FILE, Client
from biocompute.exceptions import BiocomputeError


def _save_config(config: dict[str, str]) -> None:
    """Save config to ~/.lbc/config.toml."""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{k} = "{v}"' for k, v in config.items()]
    _CONFIG_FILE.write_text("\n".join(lines) + "\n")


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
    """Configure API key, server URL, and challenge ID."""
    api_key = click.prompt("API key")
    base_url = click.prompt("Server URL", default="https://lbc.fly.dev")
    challenge_id = click.prompt("Challenge ID", default="default")

    click.echo("Verifying credentials...")
    try:
        client = Client(api_key=api_key, base_url=base_url, challenge_id=challenge_id)
        user = client.user()
        client.close()
    except BiocomputeError as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(1)

    _save_config({"api_key": api_key, "base_url": base_url, "challenge_id": challenge_id})
    click.echo(f"Logged in as {user['name']}. Config saved to {_CONFIG_FILE}")


@cli.command()
def logout() -> None:
    """Remove stored credentials."""
    if _CONFIG_FILE.exists():
        _CONFIG_FILE.unlink()
        click.echo("Logged out.")
    else:
        click.echo("Not logged in.")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--no-cache", is_flag=True, help="Disable submission caching.")
def run(file: str, no_cache: bool) -> None:
    """Run an experiment script.

    FILE is a Python script that uses the biocompute API (Client, wells, etc.)
    directly.  The entire module is executed top-to-bottom — no special function
    name is required.
    """
    path = Path(file).resolve()
    # Add the script's directory to sys.path so local imports work
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    spec = importlib.util.spec_from_file_location("__main__", path)
    if spec is None or spec.loader is None:
        click.echo(f"Cannot load {file}", err=True)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Script error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def submit(file: str) -> None:
    """Submit an experiment file.

    FILE should be a Python file containing an `experiment` function.
    """
    path = Path(file).resolve()
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
        result = client.submit(fn)
        click.echo(f"Experiment {result.experiment_id}: {result.status}")
        if result.result_data:
            click.echo(f"Result: {result.result_data}")
        if result.error:
            click.echo(f"Error: {result.error}")
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


@cli.command()
def experiments() -> None:
    """List all experiments."""
    client = _get_client()
    try:
        data = client.list_experiments()
        if not data:
            click.echo("No experiments found.")
            return
        for exp in data:
            status = exp.get("status", "unknown")
            exp_id = exp.get("id", "?")
            click.echo(f"  {exp_id}  {status}")
    except BiocomputeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        client.close()


@cli.command()
@click.argument("experiment_id")
def show(experiment_id: str) -> None:
    """Show details for an experiment."""
    client = _get_client()
    try:
        exp: dict[str, Any] = client.get_experiment(experiment_id)
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
