from typing import Optional
from tfstate.models import State


_current_state: Optional[State] = None
_state_source: Optional[str] = None


def set_state(state: State, source: str) -> None:
    global _current_state, _state_source
    _current_state = state
    _state_source = source


def get_state() -> Optional[State]:
    return _current_state


def get_state_source() -> Optional[str]:
    return _state_source


def clear_state() -> None:
    global _current_state, _state_source
    _current_state = None
    _state_source = None


def require_state() -> State:
    if _current_state is None:
        raise RuntimeError("No state loaded. Run 'tfstate init' first.")
    return _current_state
