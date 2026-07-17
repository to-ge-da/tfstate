import json
from pathlib import Path
from typing import Any, Optional

import typer

from tfstate import debug
from tfstate.attrs import get_attr, is_missing, parse_attr_path
from tfstate.models import State
from tfstate.output import print_query
from tfstate.parser import StateParseError, parse_state_file
from tfstate.session import load_session
from tfstate.state_store import require_state


def query(
    state_file: Optional[Path] = None,
    type: Optional[str] = None,
    module: Optional[str] = None,
    attrs: Optional[list[str]] = None,
    has_attrs: Optional[list[str]] = None,
    missing_attrs: Optional[list[str]] = None,
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

    addresses: list[str] = []
    for resource in state.resources:
        if type is not None and resource.type != type:
            continue
        if module is not None and resource.module != module:
            continue
        for index, instance in enumerate(resource.instances):
            if not _matches_attributes(
                instance.attributes,
                attr_filters,
                has_attr_filters,
                missing_attr_filters,
            ):
                continue
            addresses.append(resource.full_address(index))

    print_query(addresses)


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
