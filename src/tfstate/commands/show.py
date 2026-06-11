import typer
from pathlib import Path
from tfstate.parser import parse_state_file, StateParseError
from tfstate.output import print_show


def show(state_file: Path) -> None:
    try:
        state = parse_state_file(state_file)
        print_show(state, str(state_file))
    except StateParseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(show)