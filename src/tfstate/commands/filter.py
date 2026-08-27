from pathlib import Path
from typing import Optional

from tfstate import debug
from tfstate.output import print_filter
from tfstate.parser import StateParseError, parse_state_file, write_state_file


def filter_state(
    state_file: Path,
    output: Path,
    types: Optional[list[str]] = None,
    modules: Optional[list[str]] = None,
    exclude_types: Optional[list[str]] = None,
    exclude_modules: Optional[list[str]] = None,
) -> None:
    try:
        debug.logger.debug("Loading state from file: %s", state_file)
        state = parse_state_file(state_file)
        filtered = state.filtered(
            types=types or (),
            modules=modules or (),
            exclude_types=exclude_types or (),
            exclude_modules=exclude_modules or (),
        )
        write_state_file(output, filtered)
        print_filter(output, filtered)
    except StateParseError as e:
        debug.exit_with_traceback(e)
    except Exception as e:
        debug.exit_with_traceback(e)
