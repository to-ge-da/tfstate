import typer
from pathlib import Path
from typing import Optional
from tfstate.parser import parse_state_file, StateParseError
from tfstate.output import print_show
from tfstate.state_store import get_state_source, get_backend_type, require_state
from tfstate.session import load_session


def show(state_file: Optional[Path] = None) -> None:
    try:
        if state_file:
            state = parse_state_file(state_file)
            print_show(state, str(state_file))
            return

        state = require_state()
        source = get_state_source() or "unknown"
        backend_type = get_backend_type()
    except StateParseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except RuntimeError:
        cached = load_session()
        if cached is None:
            typer.echo("Error: No state loaded. Run 'tfstate init' first.", err=True)
            raise typer.Exit(1)
        state, source, backend, _, _ = cached
        backend_type = backend

    print_show(state, source, backend_type=backend_type)


if __name__ == "__main__":
    typer.run(show)
