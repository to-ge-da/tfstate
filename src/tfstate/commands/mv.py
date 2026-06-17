import typer
import subprocess
from pathlib import Path
from typing import Optional

from tfstate import debug
from tfstate.state_store import (
    require_state,
    require_terraform_mode,
    get_state_source,
    get_backend_type,
    set_state,
)
from tfstate.parser import parse_state_json
from tfstate.session import save_session, load_session
from tfstate.output import print_mv, console, resolve_yes


def mv(
    src: str,
    dst: str,
    yes: bool = False,
    force: bool = False,
    backup: Optional[str] = None,
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

    if not state.get_resource(src):
        typer.echo(f"Error: Source resource not found in state: {src}", err=True)
        raise typer.Exit(1)

    if state.get_resource(dst):
        typer.echo(
            f"Error: Target address already exists in state: {dst}. "
            "Refusing to overwrite.",
            err=True,
        )
        raise typer.Exit(1)

    if not yes:
        if not typer.confirm(f"Are you sure you want to move {src} to {dst}?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        backup_path: Optional[Path] = None
        if backup:
            backup_path = Path(backup)
        else:
            backup_path = Path(workspace) / "terraform.tfstate.backup"
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

        debug.logger.debug("Running: terraform state mv %s %s", src, dst)
        mv_result = subprocess.run(
            ["terraform", "state", "mv", src, dst],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if mv_result.returncode != 0:
            raise RuntimeError(f"terraform state mv failed:\n{mv_result.stderr}")

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
                    "[yellow]Warning: could not refresh state after move. "
                    "Run 'tfstate show' to verify.[/yellow]"
                )
        except Exception as e:
            console.print(
                f"[yellow]Warning: state refresh failed ({e}). "
                "The move succeeded but the cached state may be stale.[/yellow]"
            )

        print_mv(src, dst, str(backup_path), new_state, mv_result.stdout)

    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        debug.exit_with_traceback(e)


if __name__ == "__main__":
    typer.run(mv)
