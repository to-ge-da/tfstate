import logging
import traceback
import typer

logger = logging.getLogger("tfstate")
_debug_enabled = False


def configure(debug: bool) -> None:
    global _debug_enabled
    _debug_enabled = debug
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)


def is_debug() -> bool:
    return _debug_enabled


def exit_with_traceback(e: Exception) -> None:
    if _debug_enabled:
        typer.echo(traceback.format_exc(), err=True)
    else:
        typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(1)
