from tfstate import debug
from tfstate.session import clear_session
from tfstate.output import print_clear


def clear() -> None:
    try:
        clear_session()
        print_clear()
    except Exception as e:
        debug.exit_with_traceback(e)
