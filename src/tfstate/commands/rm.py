import os
import sys
import typer
import subprocess
from pathlib import Path
from typing import Optional

import questionary
from questionary import Style

from tfstate import debug
from tfstate.models import State
from tfstate.state_store import (
    require_state,
    require_terraform_mode,
    get_state_source,
    get_backend_type,
    set_state,
)
from tfstate.parser import parse_state_json
from tfstate.session import save_session, load_session
from tfstate.output import print_rm, console, resolve_yes


_RM_PICKER_STYLE = Style(
    [
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff bold"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#ffffff bg:#005fff bold"),
        ("selected", "fg:#ffffff bg:#005fff bold"),
        ("text", "fg:#a8a8a8"),
        ("instruction", "fg:#808080"),
    ]
)


def rm(
    address: Optional[str] = None,
    yes: bool = False,
    force: bool = False,
    backup: Optional[str] = None,
    no_backup: bool = False,
    interactive: bool = False,
) -> None:
    yes = resolve_yes(yes, force)

    if interactive and address:
        typer.echo("Error: ADDRESS cannot be combined with --interactive.", err=True)
        raise typer.Exit(1)

    if not interactive and not address:
        typer.echo(
            "Error: Missing argument 'ADDRESS'. Use --interactive to select resources.",
            err=True,
        )
        raise typer.Exit(1)

    state, workspace = _load_connected_state()

    if interactive:
        _run_interactive(state, workspace, yes=yes, backup=backup, no_backup=no_backup)
        return

    assert address is not None
    if not state.get_resource(address):
        typer.echo(f"Error: Resource not found in state: {address}", err=True)
        raise typer.Exit(1)

    if not yes:
        if not typer.confirm(f"Are you sure you want to remove {address} from state?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)

    _execute_rm([address], workspace, state, backup, no_backup)


def _load_connected_state() -> tuple[State, str]:
    try:
        state = require_state()
        workspace = require_terraform_mode()
        return state, workspace
    except RuntimeError as e:
        cached = load_session()
        if cached is None:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
        state, source, backend, terraform_mode, workspace = cached
        if not terraform_mode or not workspace:
            typer.echo(
                "Error: State manipulation requires terraform mode. "
                "Run 'tfstate init --terraform' first.",
                err=True,
            )
            raise typer.Exit(1)
        set_state(state, source, backend)
        return state, workspace


def _run_interactive(
    state: State,
    workspace: str,
    *,
    yes: bool,
    backup: Optional[str],
    no_backup: bool,
) -> None:
    _require_interactive_terminal()
    addresses = _collect_addresses(state)
    if not addresses:
        console.print("[yellow]No resources in state.[/yellow]")
        raise typer.Exit(0)

    selected = _select_addresses(addresses)
    if not selected:
        console.print("[yellow]No resources selected. Operation cancelled.[/yellow]")
        raise typer.Exit(0)

    _print_preview(selected)
    if not yes:
        n = len(selected)
        prompt = (
            f"Are you sure you want to remove {selected[0]} from state?"
            if n == 1
            else f"Are you sure you want to remove {n} resources from state?"
        )
        if not typer.confirm(prompt):
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)

    _execute_rm(selected, workspace, state, backup, no_backup)


def _require_interactive_terminal() -> None:
    if not _is_tty():
        typer.echo("Error: interactive mode requires a terminal.", err=True)
        raise typer.Exit(1)
    if _is_dumb_term():
        typer.echo("Error: TERM=dumb does not support interactive mode.", err=True)
        raise typer.Exit(1)


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _is_dumb_term() -> bool:
    return os.environ.get("TERM", "") == "dumb"


def _collect_addresses(state: State) -> list[str]:
    addresses: list[str] = []
    for resource in state.resources:
        for index in range(len(resource.instances)):
            addresses.append(resource.full_address(index))
    return addresses


def _select_addresses(addresses: list[str]) -> list[str]:
    try:
        selected = questionary.checkbox(
            "Select resources to remove:",
            choices=addresses,
            style=_RM_PICKER_STYLE,
        ).ask()
    except KeyboardInterrupt:
        raise typer.Exit(130)

    if selected is None:
        raise typer.Exit(130)

    return selected


def _print_preview(addresses: list[str]) -> None:
    console.print("[bold]The following resources will be removed:[/bold]")
    for addr in addresses:
        console.print(f"  - {addr}")


def _execute_rm(
    addresses: list[str],
    workspace: str,
    state: State,
    backup: Optional[str],
    no_backup: bool,
) -> None:
    try:
        backup_path: Optional[Path] = None
        if not no_backup:
            backup_path = Path(backup) if backup else Path(workspace) / "terraform.tfstate.backup"
            try:
                debug.logger.debug("Running: terraform state pull (backup)")
                pull_result = subprocess.run(
                    ["terraform", "state", "pull"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                )
                if pull_result.returncode != 0:
                    raise RuntimeError(f"terraform state pull failed:\n{pull_result.stderr}")
                backup_path.write_text(pull_result.stdout)
            except OSError as e:
                raise RuntimeError(f"Cannot create backup at {backup_path}: {e}")

        debug.logger.debug("Running: terraform state rm %s", " ".join(addresses))
        rm_result = subprocess.run(
            ["terraform", "state", "rm", *addresses],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if rm_result.returncode != 0:
            raise RuntimeError(f"terraform state rm failed:\n{rm_result.stderr}")

        new_state = state
        try:
            pull_result = subprocess.run(
                ["terraform", "state", "pull"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            if pull_result.returncode == 0:
                new_state = parse_state_json(pull_result.stdout)
                source = get_state_source() or "unknown"
                backend = get_backend_type()
                set_state(new_state, source, backend)
                save_session(new_state, source, backend, terraform_mode=True, workspace=workspace)
            else:
                console.print(
                    "[yellow]Warning: could not refresh state after removal. "
                    "Run 'tfstate show' to verify.[/yellow]"
                )
        except Exception as e:
            console.print(
                f"[yellow]Warning: state refresh failed ({e}). "
                "The removal succeeded but the cached state may be stale.[/yellow]"
            )

        printed = addresses[0] if len(addresses) == 1 else addresses
        print_rm(
            printed, str(backup_path) if backup_path else "(none)", new_state, rm_result.stdout
        )

    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        debug.exit_with_traceback(e)


if __name__ == "__main__":
    typer.run(rm)
