import typer
from pathlib import Path
from typing import Optional
from tfstate import debug
from tfstate.parser import parse_state_file, StateParseError
from tfstate.output import print_list
from tfstate.state_store import require_state
from tfstate.session import load_session


def list_resources(
    state_file: Optional[Path] = None,
    type: Optional[str] = None,
    module: Optional[str] = None,
    show_all_types: bool = False,
) -> None:
    try:
        if state_file:
            debug.logger.debug("Loading state from file: %s", state_file)
            state = parse_state_file(state_file)
        else:
            state = require_state()
        print_list(state, resource_type=type, module=module, show_all_types=show_all_types)
    except StateParseError as e:
        debug.exit_with_traceback(e)
    except RuntimeError:
        debug.logger.debug("No in-memory state, falling back to session cache")
        cached = load_session()
        if cached is None:
            debug.logger.debug("No session cache found either")
            typer.echo("Error: No state loaded. Run 'tfstate init' first.", err=True)
            raise typer.Exit(1)
        state, _, _, _, _ = cached
        print_list(state, resource_type=type, module=module, show_all_types=show_all_types)
    except Exception as e:
        debug.exit_with_traceback(e)
        return


if __name__ == "__main__":
    typer.run(list_resources)
