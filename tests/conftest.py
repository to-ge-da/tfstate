import pytest
from pathlib import Path
from tfstate.parser import parse_state_file
from tfstate.models import State
from tfstate import debug
from tfstate.output import configure as configure_output


@pytest.fixture(autouse=True)
def reset_output_format():
    configure_output("rich")
    debug.reset()
    yield
    configure_output("rich")
    debug.reset()


@pytest.fixture
def basic_state() -> State:
    return parse_state_file(Path(__file__).parent / "fixtures" / "basic.json")


@pytest.fixture
def basic_data() -> dict:
    import json
    with open(Path(__file__).parent / "fixtures" / "basic.json") as f:
        return json.load(f)