from typing import Optional
from tfstate.models import State


_current_state: Optional[State] = None
_state_source: Optional[str] = None
_is_terraform_mode: bool = False
_terraform_workspace: Optional[str] = None
_backend_config: Optional[dict] = None
_workspace_path: Optional[str] = None


def set_state(state: State, source: str) -> None:
    global _current_state, _state_source
    _current_state = state
    _state_source = source


def get_state() -> Optional[State]:
    return _current_state


def get_state_source() -> Optional[str]:
    return _state_source


def set_workspace(path: str) -> None:
    global _workspace_path
    _workspace_path = path


def get_workspace() -> Optional[str]:
    return _workspace_path


def clear_state() -> None:
    global \
        _current_state, \
        _state_source, \
        _is_terraform_mode, \
        _terraform_workspace, \
        _backend_config, \
        _workspace_path
    _current_state = None
    _state_source = None
    _is_terraform_mode = False
    _terraform_workspace = None
    _backend_config = None
    _workspace_path = None


def require_state() -> State:
    if _current_state is None:
        raise RuntimeError("No state loaded. Run 'tfstate init' first.")
    return _current_state


def set_terraform_mode(workspace: str, backend_config: dict) -> None:
    global _is_terraform_mode, _terraform_workspace, _backend_config
    _is_terraform_mode = True
    _terraform_workspace = workspace
    _backend_config = backend_config


def is_terraform_mode() -> bool:
    return _is_terraform_mode


def get_terraform_workspace() -> Optional[str]:
    return _terraform_workspace


def get_backend_config() -> Optional[dict]:
    return _backend_config
