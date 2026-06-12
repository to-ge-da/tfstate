import typer
from pathlib import Path
from typing import Optional, Annotated

from tfstate.commands.show import show
from tfstate.commands.list import list_resources
from tfstate.commands.pull import pull
from tfstate.commands.init import init as init_cmd

app = typer.Typer(
    name="tfstate",
    help="A CLI tool for debugging, analyzing, and manipulating Terraform state files",
)


@app.command("init")
def init(
    state_path: str = typer.Argument(..., help="S3 URI or local file path to state file"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    debug: Annotated[bool, typer.Option("--debug", help="Show full stack traces")] = False,
) -> None:
    init_cmd(state_path, profile=profile, region=region, debug=debug)


@app.command("show")
def show_cmd(state_file: Path) -> None:
    show(state_file)


@app.command("list")
def list_cmd(
    state_file: Path,
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Filter by module"),
) -> None:
    list_resources(state_file, type=type, module=module)


@app.command("pull")
def pull_cmd(
    s3_uri: str,
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
) -> None:
    pull(s3_uri, output=output, profile=profile, region=region)


def main() -> None:
    app()


if __name__ == "__main__":
    main()