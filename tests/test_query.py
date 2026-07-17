import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.session import clear_session
from tfstate.state_store import clear_state


runner = CliRunner()
BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"


@pytest.fixture(autouse=True)
def clear_loaded_state():
    clear_state()
    clear_session()


@pytest.fixture
def typed_fixture(tmp_path):
    data = json.loads(BASIC_FIXTURE.read_text())
    attributes = data["resources"][2]["instances"][0]["attributes"]
    attributes.update(
        {
            "enabled": True,
            "count": 3,
            "nullable": None,
            "ports": [80, 443],
            "tags": {"Environment": "prod", "Owner": "platform"},
        }
    )
    path = tmp_path / "typed.json"
    path.write_text(json.dumps(data))
    return path


def test_query_without_filters_returns_every_instance():
    result = runner.invoke(app, ["--format", "json", "query", str(BASIC_FIXTURE)])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        "module.vpc.aws_vpc.main",
        "module.vpc.aws_subnet.public[0]",
        "module.vpc.aws_subnet.public[1]",
        "aws_instance.bastion",
    ]


def test_query_filters_by_type_and_module_with_and_semantics():
    result = runner.invoke(
        app,
        [
            "query",
            str(BASIC_FIXTURE),
            "--type",
            "aws_vpc",
            "--module",
            "module.vpc",
        ],
    )

    assert result.exit_code == 0
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "aws_subnet" not in result.stdout


def test_query_repeatable_attributes_and_typed_values(typed_fixture):
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--attr",
            "tags.Environment=prod",
            "--attr",
            "enabled=true",
            "--attr",
            "count=3",
            "--attr",
            "ports=[80, 443]",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == ["aws_instance.bastion"]


def test_query_has_and_missing_attributes_distinguish_null(typed_fixture):
    present = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--has-attr",
            "nullable",
            "--has-attr",
            "tags.Owner",
        ],
    )
    missing = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--missing-attr",
            "tags.CostCenter",
            "--type",
            "aws_instance",
        ],
    )

    assert present.exit_code == 0
    assert json.loads(present.stdout) == ["aws_instance.bastion"]
    assert missing.exit_code == 0
    assert json.loads(missing.stdout) == ["aws_instance.bastion"]


def test_query_list_index_path(typed_fixture):
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--attr",
            "ports[1]=443",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == ["aws_instance.bastion"]


def test_query_no_match_contracts():
    rich = runner.invoke(
        app, ["query", str(BASIC_FIXTURE), "--type", "nonexistent"]
    )
    plain = runner.invoke(
        app,
        ["--format", "plain", "query", str(BASIC_FIXTURE), "--type", "nonexistent"],
    )
    json_result = runner.invoke(
        app,
        ["--format", "json", "query", str(BASIC_FIXTURE), "--type", "nonexistent"],
    )

    assert rich.exit_code == plain.exit_code == json_result.exit_code == 0
    assert "No resources matched the query." in rich.stdout
    assert "No resources matched the query." in plain.stdout
    assert json.loads(json_result.stdout) == []


@pytest.mark.parametrize("expression", ["invalid", "=value", "tags."])
def test_query_rejects_malformed_attr_filter(expression):
    result = runner.invoke(
        app, ["query", str(BASIC_FIXTURE), "--attr", expression]
    )

    assert result.exit_code == 2
    assert "--attr" in result.output


def test_query_rejects_invalid_presence_path():
    result = runner.invoke(
        app, ["query", str(BASIC_FIXTURE), "--has-attr", "rules[x]"]
    )

    assert result.exit_code == 2
    assert "--has-attr" in result.output


def test_query_connected_after_init():
    assert runner.invoke(app, ["init", str(BASIC_FIXTURE)]).exit_code == 0

    result = runner.invoke(app, ["query", "--type", "aws_instance"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "aws_instance.bastion"


def test_query_without_loaded_state_fails():
    result = runner.invoke(app, ["query", "--type", "aws_instance"])

    assert result.exit_code == 1
    assert "No state loaded" in result.output


def test_query_help():
    result = runner.invoke(app, ["query", "--help"])

    assert result.exit_code == 0
    assert "STATE_FILE" in result.stdout
    assert "--type" in result.stdout
    assert "--module" in result.stdout
    assert "--attr" in result.stdout
    assert "--has-attr" in result.stdout
    assert "--missing-attr" in result.stdout
