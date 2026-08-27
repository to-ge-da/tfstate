import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import questionary
import typer
from questionary import Style

from tfstate import debug
from tfstate.attrs import get_attr, is_missing, parse_attr_path
from tfstate.models import State
from tfstate.output import get_format, print_get, print_query
from tfstate.parser import StateParseError, parse_state_file
from tfstate.session import load_session
from tfstate.state_store import require_state


_QUERY_PICKER_STYLE = Style(
    [
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff bold"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#ffffff bg:#005fff bold"),
        ("selected", "fg:#ffffff bg:#005fff bold"),
        ("text", "fg:#a8a8a8"),
        ("instruction", "fg:#808080"),
    ]
)


def query(
    state_file: Optional[Path] = None,
    type: Optional[str] = None,
    module: Optional[str] = None,
    attrs: Optional[list[str]] = None,
    has_attrs: Optional[list[str]] = None,
    missing_attrs: Optional[list[str]] = None,
    interactive: bool = False,
) -> None:
    try:
        attr_filters = [_parse_attr_filter(expression) for expression in attrs or []]
        has_attr_filters = _validate_paths(has_attrs or [], "--has-attr")
        missing_attr_filters = _validate_paths(missing_attrs or [], "--missing-attr")
        state = _load_state(state_file)
    except typer.BadParameter:
        raise
    except StateParseError as e:
        debug.exit_with_traceback(e)
        return
    except RuntimeError:
        typer.echo("Error: No state loaded. Run 'tfstate init' first.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        debug.exit_with_traceback(e)
        return

    has_filters = any(
        (
            type is not None,
            module is not None,
            bool(attr_filters),
            bool(has_attr_filters),
            bool(missing_attr_filters),
        )
    )
    addresses = _collect_addresses(
        state,
        type=type,
        module=module,
        attr_filters=attr_filters,
        has_attrs=has_attr_filters,
        missing_attrs=missing_attr_filters,
    )

    if _should_run_interactive(interactive=interactive, has_filters=has_filters):
        _run_interactive(state, addresses)
        return

    print_query(addresses)


def _should_run_interactive(*, interactive: bool, has_filters: bool) -> bool:
    fmt = get_format()

    if interactive and fmt in ("json", "plain"):
        typer.echo(
            "Error: --interactive cannot be used with --format json or plain.",
            err=True,
        )
        raise typer.Exit(1)

    if fmt != "rich":
        return False

    if interactive:
        if not _is_tty():
            typer.echo("Error: interactive mode requires a terminal.", err=True)
            raise typer.Exit(1)
        if _is_dumb_term():
            typer.echo(
                "Warning: TERM=dumb does not support interactive mode; "
                "falling back to non-interactive output.",
                err=True,
            )
            return False
        return True

    if has_filters:
        return False

    if _is_dumb_term():
        if _is_tty():
            typer.echo(
                "Warning: TERM=dumb does not support interactive mode; "
                "falling back to non-interactive output.",
                err=True,
            )
            return False
        typer.echo(_bare_non_tty_message(), err=True)
        raise typer.Exit(1)

    if _is_tty():
        return True

    typer.echo(_bare_non_tty_message(), err=True)
    raise typer.Exit(1)


def _bare_non_tty_message() -> str:
    return (
        "Error: bare query requires a terminal for interactive mode. "
        "Use 'tfstate list' for inventory, add filters, or use --interactive."
    )


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _is_dumb_term() -> bool:
    return os.environ.get("TERM", "") == "dumb"


def _run_interactive(state: State, addresses: list[str]) -> None:
    if not addresses:
        print_query(addresses)
        return
    if len(addresses) == 1:
        print_get(state, addresses[0])
        return

    try:
        selected = questionary.select(
            "Select a resource:",
            choices=addresses,
            pointer="➜",
            style=_QUERY_PICKER_STYLE,
        ).ask()
    except KeyboardInterrupt:
        raise typer.Exit(130)

    if selected is None:
        raise typer.Exit(130)

    print_get(state, selected)


def _collect_addresses(
    state: State,
    *,
    type: Optional[str],
    module: Optional[str],
    attr_filters: list[tuple[str, Any]],
    has_attrs: list[str],
    missing_attrs: list[str],
) -> list[str]:
    addresses: list[str] = []
    for resource in state.resources:
        if not resource.selected(
            types=(type,) if type is not None else (),
            modules=(module,) if module is not None else (),
        ):
            continue
        for index, instance in enumerate(resource.instances):
            if not _matches_attributes(
                instance.attributes,
                attr_filters,
                has_attrs,
                missing_attrs,
            ):
                continue
            addresses.append(resource.full_address(index))
    return addresses


def _parse_attr_filter(expression: str) -> tuple[str, Any]:
    if "=" not in expression:
        raise typer.BadParameter(f"expected KEY=VALUE, got {expression!r}", param_hint="--attr")
    path, raw_value = expression.split("=", 1)
    if not path:
        raise typer.BadParameter("attribute key cannot be empty", param_hint="--attr")
    try:
        parse_attr_path(path)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--attr") from e

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value
    return path, value


def _validate_paths(paths: list[str], option: str) -> list[str]:
    for path in paths:
        try:
            parse_attr_path(path)
        except ValueError as e:
            raise typer.BadParameter(str(e), param_hint=option) from e
    return paths


def _matches_attributes(
    attributes: dict,
    attr_filters: list[tuple[str, Any]],
    has_attrs: list[str],
    missing_attrs: list[str],
) -> bool:
    if any(get_attr(attributes, path) != expected for path, expected in attr_filters):
        return False
    if any(is_missing(get_attr(attributes, path)) for path in has_attrs):
        return False
    if any(not is_missing(get_attr(attributes, path)) for path in missing_attrs):
        return False
    return True


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
