import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tfstate.models import State
from tfstate.parser import parse_state_json


SESSION_DIR = Path.home() / ".tfstate"
SESSION_FILE = SESSION_DIR / "session.json"
STATE_FILE = SESSION_DIR / "state.json"


def save_session(
    state: State,
    source: str,
    backend: Optional[str] = None,
    terraform_mode: bool = False,
    workspace: Optional[str] = None,
) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    state_json = state.model_dump_json(indent=2)
    STATE_FILE.write_text(state_json)

    metadata = {
        "source": source,
        "backend": backend,
        "terraform_mode": terraform_mode,
        "workspace": workspace,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    SESSION_FILE.write_text(json.dumps(metadata, indent=2))


def load_session() -> Optional[tuple[State, str, Optional[str], bool, Optional[str]]]:
    if not SESSION_FILE.exists() or not STATE_FILE.exists():
        return None

    try:
        metadata = json.loads(SESSION_FILE.read_text())
        state = parse_state_json(STATE_FILE.read_text())

        return (
            state,
            metadata.get("source", "unknown"),
            metadata.get("backend"),
            metadata.get("terraform_mode", False),
            metadata.get("workspace"),
        )
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def clear_session() -> None:
    if SESSION_DIR.exists():
        shutil.rmtree(SESSION_DIR)
