import typer
import subprocess
import traceback
from pathlib import Path
from typing import Optional

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


def rm(
    address: str,
    yes: bool = False,
    force: bool = False,
    backup: Optional[str] = None,
    no_backup: bool = False,
    debug: bool = False,
) -> None:
    yes = resolve_yes(yes, force)

    try:
        state = require_state()
        workspace = require_terraform_mode()
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

    if not state.get_resource(address):
        typer.echo(f"Error: Resource not found in state: {address}", err=True)
        raise typer.Exit(1)

    if not yes:
        if not typer.confirm(f"Are you sure you want to remove {address} from state?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        backup_path: Optional[Path] = None
        if not no_backup:
            backup_path = Path(backup) if backup else Path(workspace) / "terraform.tfstate.backup"
            try:
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

        rm_result = subprocess.run(
            ["terraform", "state", "rm", address],
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
                save_session(
                    new_state, source, backend, terraform_mode=True, workspace=workspace
                )
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

        print_rm(address, str(backup_path) if backup_path else "(none)", new_state, rm_result.stdout)

    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        if debug:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(rm)
