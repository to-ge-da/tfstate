import typer
from pathlib import Path
from typing import Optional
from tfstate.parser import parse_state_file, StateParseError
from tfstate.output import print_list
from tfstate.state_store import require_state


def list_resources(
    state_file: Optional[Path] = None,
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Filter by module"),
) -> None:
    try:
        if state_file:
            state = parse_state_file(state_file)
        else:
            state = require_state()
        print_list(state, resource_type=type, module=module)
    except StateParseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(list_resources)
