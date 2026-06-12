import typer
from pathlib import Path
from typing import Optional
from tfstate.parser import parse_state_file, StateParseError
from tfstate.output import print_list


def list_resources(
    state_file: Path,
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Filter by module"),
) -> None:
    try:
        state = parse_state_file(state_file)
        print_list(state, resource_type=type, module=module)
    except StateParseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(list_resources)