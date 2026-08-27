import pytest
from tfstate.parser import parse_state_file, parse_state_data, StateParseError
from pathlib import Path


class TestParseStateData:
    def test_parses_valid_data(self, basic_data):
        state = parse_state_data(basic_data)
        assert state.version == 4
        assert state.serial == 42
        assert len(state.resources) == 3

    def test_handles_missing_optional_fields(self, basic_data):
        del basic_data["outputs"]
        del basic_data["serial"]
        state = parse_state_data(basic_data)
        assert state.outputs == {}
        assert state.serial == 0

    def test_handles_missing_lineage(self, basic_data):
        del basic_data["lineage"]
        state = parse_state_data(basic_data)
        assert state.lineage == ""

    def test_handles_missing_instances(self, basic_data):
        basic_data["resources"][0]["instances"] = []
        state = parse_state_data(basic_data)
        assert len(state.resources[0].instances) == 0

    def test_parses_string_and_int_index_key(self):
        path = Path(__file__).parent / "fixtures" / "foreach.json"
        state = parse_state_file(path)
        buckets = state.resources[0].instances
        assert buckets[0].index_key == "logs"
        assert buckets[1].index_key == "backups"
        webs = state.resources[1].instances
        assert webs[0].index_key == 0
        assert webs[1].index_key == 1
        assert isinstance(webs[0].index_key, int)


class TestParseStateFile:
    def test_parses_fixture_file(self):
        path = Path(__file__).parent / "fixtures" / "basic.json"
        state = parse_state_file(path)
        assert state.version == 4
        assert len(state.resources) == 3

    def test_raises_on_nonexistent_file(self):
        with pytest.raises(StateParseError, match="Cannot read file"):
            parse_state_file(Path("/nonexistent/file.json"))

    def test_raises_on_invalid_json(self, tmp_path):
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json")
        with pytest.raises(StateParseError, match="Invalid JSON"):
            parse_state_file(invalid_file)