from difflib import get_close_matches
from pathlib import Path
from typing import Optional

import typer

from tfstate import debug
from tfstate.models import State
from tfstate.output import print_get
from tfstate.parser import StateParseError, parse_state_file
from tfstate.session import load_session
from tfstate.state_store import require_state


def get(target: str, address: Optional[str] = None) -> None:
    state_file = Path(target) if address is not None else None
    resource_address = address or target

    try:
        state = _load_state(state_file)
    except StateParseError as e:
        debug.exit_with_traceback(e)
        return
    except RuntimeError:
        typer.echo("Error: No state loaded. Run 'tfstate init' first.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        debug.exit_with_traceback(e)
        return

    ambiguous = next(
        (
            resource
            for resource in state.resources
            if resource.address == resource_address and len(resource.instances) > 1
        ),
        None,
    )
    if ambiguous:
        typer.echo(f"Error: Resource address is ambiguous: {resource_address}", err=True)
        typer.echo("Use an indexed address:", err=True)
        for index in range(len(ambiguous.instances)):
            typer.echo(f"  - {ambiguous.full_address(index)}", err=True)
        raise typer.Exit(1)

    if state.get_resource(resource_address) is None:
        typer.echo(f"Error: Resource not found: {resource_address}", err=True)
        suggestions = get_close_matches(
            resource_address, _resource_addresses(state), n=3, cutoff=0.6
        )
        if suggestions:
            typer.echo("Did you mean:", err=True)
            for suggestion in suggestions:
                typer.echo(f"  - {suggestion}", err=True)
        raise typer.Exit(1)

    print_get(state, resource_address)


def _load_state(state_file: Optional[Path]) -> State:
    if state_file is not None:
        debug.logger.debug("Loading state from file: %s", state_file)
        return parse_state_file(state_file)

    try:
        return require_state()
    except RuntimeError:
        debug.logger.debug("No in-memory state, falling back to session cache")
        cached = load_session()
        if cached is None:
            debug.logger.debug("No session cache found either")
            raise
        state, _, _, _, _ = cached
        return state


def _resource_addresses(state: State) -> list[str]:
    return [
        resource.full_address(index)
        for resource in state.resources
        for index in range(len(resource.instances))
    ]
