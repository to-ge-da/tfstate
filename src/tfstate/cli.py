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
from tfstate.commands.cache import clear as cache_clear
from tfstate.output import OutputFormat, configure as configure_output

app = typer.Typer(
    name="tfstate",
    help="A CLI tool for debugging, analyzing, and manipulating Terraform state files",
)
cache_app = typer.Typer(
    name="cache",
    help="Manage session and workspace cache.",
    no_args_is_help=True,
)

DebugOption = Annotated[bool, typer.Option("--debug", help="Show full stack traces")]
FormatOption = Annotated[
    OutputFormat, typer.Option("--format", "-f", help="Output format: rich, json, plain")
]


def configure_globals(debug: bool, format: OutputFormat) -> None:
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
    fresh: Annotated[
        bool,
        typer.Option(
            "--fresh",
            help="Ignore cached terraform workspace (use a new temp dir)",
        ),
    ] = False,
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Initialize state from a local file or S3 backend."""
    configure_globals(debug, format)
    init_cmd(
        state_path,
        profile=profile,
        region=region,
        terraform=terraform,
        output=output,
        fresh=fresh,
    )


@app.command("show")
def show_cmd(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Show state metadata and resource summary."""
    configure_globals(debug, format)
    show(state_file)


@app.command("list")
def list_cmd(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(
        None, "--module", "-m", help="Filter by module path prefix"
    ),
    show_all_types: Annotated[
        bool, typer.Option("--show-all-types", help="Show all available types without truncation")
    ] = False,
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """List resources in state."""
    configure_globals(debug, format)
    list_resources(state_file, type=type, module=module, show_all_types=show_all_types)


@app.command("get")
def get(
    target: str = typer.Argument(
        ..., help="Resource address, or state file when ADDRESS is also provided"
    ),
    address: Optional[str] = typer.Argument(
        None, help="Resource address when reading an offline state file"
    ),
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Show detailed information about a resource."""
    configure_globals(debug, format)
    get_cmd(target, address)


@app.command("query")
def query(
    state_file: Optional[Path] = typer.Argument(
        None, help="State file (omit to use initialized state)"
    ),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    module: Optional[str] = typer.Option(
        None, "--module", "-m", help="Filter by module path prefix"
    ),
    attr: Optional[list[str]] = typer.Option(
        None, "--attr", help="Filter by attribute KEY=VALUE; repeat for AND"
    ),
    has_attr: Optional[list[str]] = typer.Option(
        None, "--has-attr", help="Require an attribute path; repeat for AND"
    ),
    missing_attr: Optional[list[str]] = typer.Option(
        None, "--missing-attr", help="Require a missing attribute path; repeat for AND"
    ),
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Force interactive resource picker (TTY required)",
        ),
    ] = False,
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Explore resources interactively, or filter them non-interactively."""
    configure_globals(debug, format)
    query_cmd(
        state_file,
        type=type,
        module=module,
        attrs=attr,
        has_attrs=has_attr,
        missing_attrs=missing_attr,
        interactive=interactive,
    )


@app.command("diff")
def diff(
    file1: Path = typer.Argument(..., help="Original Terraform state file"),
    file2: Path = typer.Argument(..., help="Updated Terraform state file"),
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Compare two state files."""
    configure_globals(debug, format)
    diff_cmd(file1, file2)


@app.command("pull")
def pull_cmd(
    s3_uri: str,
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Download state from S3."""
    configure_globals(debug, format)
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
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Move a resource to a new address."""
    configure_globals(debug, format)
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
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Remove a resource from connected state."""
    configure_globals(debug, format)
    rm_cmd(address, yes=yes, force=force, backup=backup, no_backup=no_backup)


@cache_app.command("clear")
def cache_clear_cmd(
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Clear cached session state."""
    configure_globals(debug, format)
    cache_clear()


app.add_typer(cache_app, name="cache")


@app.command(
    "clear",
    deprecated=True,
    short_help="Clear cached session state",
)
def clear_cmd(
    debug: DebugOption = False,
    format: FormatOption = OutputFormat.RICH,
) -> None:
    """Clear cached session state (deprecated: use `cache clear`)."""
    configure_globals(debug, format)
    typer.echo(
        "Warning: 'tfstate clear' is deprecated; use 'tfstate cache clear' instead.",
        err=True,
    )
    cache_clear()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
