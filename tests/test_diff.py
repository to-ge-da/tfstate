import copy
import json
from pathlib import Path

from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.commands.diff import compare_states
from tfstate.parser import parse_state_data, parse_state_file


runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
BASIC_FIXTURE = FIXTURES / "basic.json"
MODIFIED_FIXTURE = FIXTURES / "basic_modified.json"


def test_diff_rich_reports_added_removed_modified_and_summary():
    result = runner.invoke(app, ["diff", str(BASIC_FIXTURE), str(MODIFIED_FIXTURE)])

    assert result.exit_code == 0
    assert "Removed Resources:" in result.stdout
    assert "aws_instance.bastion" in result.stdout
    assert "Added Resources:" in result.stdout
    assert "aws_s3_bucket.logs" in result.stdout
    assert "Modified Resources:" in result.stdout
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "cidr_block" in result.stdout
    assert "tags.Environment" in result.stdout
    assert "instance_tenancy" in result.stdout
    assert "Attributes changed: 3" in result.stdout
    assert "Resources added: 1" in result.stdout
    assert "Resources removed: 1" in result.stdout
    assert "Resources modified: 1" in result.stdout


def test_diff_json_has_stable_schema_and_metadata_notices():
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "diff",
            str(BASIC_FIXTURE),
            str(MODIFIED_FIXTURE),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [notice["field"] for notice in data["metadata"]] == ["serial", "lineage"]
    assert data["removed"] == [
        {"address": "aws_instance.bastion", "type": "aws_instance"}
    ]
    assert data["added"] == [
        {"address": "aws_s3_bucket.logs", "type": "aws_s3_bucket"}
    ]
    modified = data["modified"][0]
    assert modified["address"] == "module.vpc.aws_vpc.main"
    assert {change["kind"] for change in modified["changes"]} == {
        "added",
        "removed",
        "changed",
    }
    assert data["summary"] == {
        "resources_added": 1,
        "resources_removed": 1,
        "resources_modified": 1,
        "attributes_changed": 3,
    }


def test_diff_plain_uses_same_sections():
    result = runner.invoke(
        app,
        [
            "--format",
            "plain",
            "diff",
            str(BASIC_FIXTURE),
            str(MODIFIED_FIXTURE),
        ],
    )

    assert result.exit_code == 0
    assert "Serial differs: 42 -> 43" in result.stdout
    assert "Removed Resources:" in result.stdout
    assert "Added Resources:" in result.stdout
    assert "Modified Resources:" in result.stdout


def test_diff_identical_files():
    rich = runner.invoke(app, ["diff", str(BASIC_FIXTURE), str(BASIC_FIXTURE)])
    json_result = runner.invoke(
        app,
        ["--format", "json", "diff", str(BASIC_FIXTURE), str(BASIC_FIXTURE)],
    )

    assert rich.exit_code == 0
    assert "No differences found" in rich.stdout
    data = json.loads(json_result.stdout)
    assert data["metadata"] == []
    assert data["removed"] == []
    assert data["added"] == []
    assert data["modified"] == []
    assert all(value == 0 for value in data["summary"].values())


def test_diff_recurses_into_lists_and_empty_containers():
    old_data = json.loads(BASIC_FIXTURE.read_text())
    new_data = copy.deepcopy(old_data)
    old_attrs = old_data["resources"][0]["instances"][0]["attributes"]
    new_attrs = new_data["resources"][0]["instances"][0]["attributes"]
    old_attrs["rules"] = [{"port": 80}, {"port": 443}]
    new_attrs["rules"] = [{"port": 8080}, {"port": 443}, {"port": 8443}]
    old_attrs["empty"] = {}
    new_attrs["empty"] = []

    result = compare_states(parse_state_data(old_data), parse_state_data(new_data))
    changes = result["modified"][0]["changes"]

    assert changes == [
        {"kind": "changed", "path": "empty", "old": {}, "new": []},
        {"kind": "changed", "path": "rules[0].port", "old": 80, "new": 8080},
        {"kind": "added", "path": "rules[2].port", "new": 8443},
    ]


def test_diff_matches_multi_instance_resources_by_full_address():
    old_state = parse_state_file(BASIC_FIXTURE)
    new_state = parse_state_file(BASIC_FIXTURE)
    new_state.resources[1].instances[1].attributes["cidr_block"] = "10.1.2.0/24"

    result = compare_states(old_state, new_state)

    assert result["modified"][0]["address"] == "module.vpc.aws_subnet.public[1]"
    assert result["modified"][0]["changes"][0]["path"] == "cidr_block"


def test_diff_ignores_provider_and_dependency_only_changes():
    old_state = parse_state_file(BASIC_FIXTURE)
    new_state = parse_state_file(BASIC_FIXTURE)
    new_state.resources[0].provider = "different-provider"
    new_state.resources[0].instances[0].dependencies = ["other.resource"]

    result = compare_states(old_state, new_state)

    assert result["modified"] == []
    assert result["summary"]["resources_modified"] == 0


def test_diff_metadata_only_still_reports_no_resource_differences(tmp_path):
    data = json.loads(BASIC_FIXTURE.read_text())
    data["serial"] += 1
    changed = tmp_path / "metadata.json"
    changed.write_text(json.dumps(data))

    result = runner.invoke(app, ["diff", str(BASIC_FIXTURE), str(changed)])

    assert result.exit_code == 0
    assert "Serial differs" in result.stdout
    assert "No differences found" in result.stdout


def test_diff_missing_file_fails():
    result = runner.invoke(
        app, ["diff", str(BASIC_FIXTURE), "/missing-state.json"]
    )

    assert result.exit_code == 1
    assert "Error" in result.output


def test_diff_help():
    result = runner.invoke(app, ["diff", "--help"])

    assert result.exit_code == 0
    assert "FILE1" in result.stdout
    assert "FILE2" in result.stdout
