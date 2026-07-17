import typer
from pathlib import Path
from typing import Optional, Annotated

from tfstate import debug as debug_module
from tfstate.commands.show import show
from tfstate.commands.list import list_resources
from tfstate.commands.get import get as get_cmd
from tfstate.commands.query import query as query_cmd
from tfstate.commands.diff import diff as diff_cmd
from tfstate.commands.pull import pull
from tfstate.commands.init import init as init_cmd
from tfstate.commands.rm import rm as rm_cmd
from tfstate.commands.mv import mv as mv_cmd
from tfstate.session import clear_session
from tfstate.output import OutputFormat, configure as configure_output, print_clear

app = typer.Typer(
    name="tfstate",
    help="A CLI tool for debugging, analyzing, and manipulating Terraform state files",
)


@app.callback()
def global_options(
    debug: Annotated[bool, typer.Option("--debug", help="Show full stack traces")] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format: rich, json, plain")
    ] = OutputFormat.RICH,
) -> None:
    debug_module.configure(debug)
    configure_output(format.value)


@app.command("init")
def init(
    state_path: str = typer.Argument(..., help="S3 URI or local file path to state file"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    terraform: Annotated[
        bool,
        typer.Option(
            "--terraform",
            help="Initialize real Terraform backend (shares providers via TF_PLUGIN_CACHE_DIR)",
        ),
    ] = False,
    output: Annotated[
        Optional[str], typer.Option("-o", "--output", help="Custom workspace directory")
    ] = None,
) -> None:
    init_cmd(state_path, profile=profile, region=region, terraform=terraform, output=output)


@app.command("show")
def show_cmd(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
) -> None:
    show(state_file)


@app.command("list")
def list_cmd(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Filter by module"),
    show_all_types: Annotated[
        bool, typer.Option("--show-all-types", help="Show all available types without truncation")
    ] = False,
) -> None:
    list_resources(state_file, type=type, module=module, show_all_types=show_all_types)


@app.command("get")
def get(
    target: str = typer.Argument(
        ..., help="Resource address, or state file when ADDRESS is also provided"
    ),
    address: Optional[str] = typer.Argument(
        None, help="Resource address when reading an offline state file"
    ),
) -> None:
    get_cmd(target, address)


@app.command("query")
def query(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Filter by module"),
    attr: Optional[list[str]] = typer.Option(
        None, "--attr", help="Filter by attribute KEY=VALUE; repeat for AND"
    ),
    has_attr: Optional[list[str]] = typer.Option(
        None, "--has-attr", help="Require an attribute path; repeat for AND"
    ),
    missing_attr: Optional[list[str]] = typer.Option(
        None, "--missing-attr", help="Require a missing attribute path; repeat for AND"
    ),
) -> None:
    query_cmd(
        state_file,
        type=type,
        module=module,
        attrs=attr,
        has_attrs=has_attr,
        missing_attrs=missing_attr,
    )


@app.command("diff")
def diff(
    file1: Path = typer.Argument(..., help="Original Terraform state file"),
    file2: Path = typer.Argument(..., help="Updated Terraform state file"),
) -> None:
    diff_cmd(file1, file2)


@app.command("pull")
def pull_cmd(
    s3_uri: str,
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
) -> None:
    pull(s3_uri, output=output, profile=profile, region=region)


@app.command("mv")
def mv(
    src: str = typer.Argument(..., help="Source resource address"),
    dst: str = typer.Argument(..., help="Destination resource address"),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    force: Annotated[
        bool, typer.Option("--force", hidden=True, help="Deprecated: use --yes")
    ] = False,
    backup: Optional[str] = typer.Option(None, "--backup", help="Custom backup path"),
) -> None:
    mv_cmd(src, dst, yes=yes, force=force, backup=backup)


@app.command("rm")
def rm(
    address: str = typer.Argument(..., help="Resource address to remove"),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    force: Annotated[
        bool, typer.Option("--force", hidden=True, help="Deprecated: use --yes")
    ] = False,
    backup: Optional[str] = typer.Option(None, "--backup", help="Custom backup path"),
    no_backup: Annotated[bool, typer.Option("--no-backup", help="Skip backup creation")] = False,
) -> None:
    rm_cmd(address, yes=yes, force=force, backup=backup, no_backup=no_backup)


@app.command("clear")
def clear_cmd() -> None:
    """Clear cached session state"""
    try:
        clear_session()
        print_clear()
    except Exception as e:
        debug_module.exit_with_traceback(e)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
