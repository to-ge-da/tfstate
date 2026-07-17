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


def test_get_offline_rich_flattens_attributes_and_lists_dependents():
    result = runner.invoke(app, ["get", str(BASIC_FIXTURE), "module.vpc.aws_vpc.main"])

    assert result.exit_code == 0
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "tags.Name" in result.stdout
    assert '"production-vpc"' in result.stdout
    assert "module.vpc.aws_subnet.public[0]" in result.stdout
    assert "module.vpc.aws_subnet.public[1]" in result.stdout
    assert "aws_instance.bastion" in result.stdout


def test_get_connected_after_init():
    assert runner.invoke(app, ["init", str(BASIC_FIXTURE)]).exit_code == 0

    result = runner.invoke(app, ["get", "aws_instance.bastion"])

    assert result.exit_code == 0
    assert "instance_type" in result.stdout
    assert '"t3.micro"' in result.stdout


def test_get_json_preserves_nested_attributes():
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "get",
            str(BASIC_FIXTURE),
            "module.vpc.aws_vpc.main",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["address"] == "module.vpc.aws_vpc.main"
    assert data["attributes"]["tags"]["Name"] == "production-vpc"
    assert data["dependents"] == [
        "module.vpc.aws_subnet.public[0]",
        "module.vpc.aws_subnet.public[1]",
        "aws_instance.bastion",
    ]


def test_get_plain_indexed_address():
    result = runner.invoke(
        app,
        [
            "--format",
            "plain",
            "get",
            str(BASIC_FIXTURE),
            "module.vpc.aws_subnet.public[1]",
        ],
    )

    assert result.exit_code == 0
    assert "Resource: module.vpc.aws_subnet.public[1]" in result.stdout
    assert "eu-west-1b" in result.stdout


def test_get_rejects_ambiguous_base_address():
    result = runner.invoke(app, ["get", str(BASIC_FIXTURE), "module.vpc.aws_subnet.public"])

    assert result.exit_code == 1
    assert "ambiguous" in result.output
    assert "module.vpc.aws_subnet.public[0]" in result.output
    assert "module.vpc.aws_subnet.public[1]" in result.output


def test_get_unknown_address_suggests_match():
    result = runner.invoke(app, ["get", str(BASIC_FIXTURE), "module.vpc.aws_vpc.mai"])

    assert result.exit_code == 1
    assert "Resource not found" in result.output
    assert "Did you mean" in result.output
    assert "module.vpc.aws_vpc.main" in result.output


def test_get_without_state_fails():
    result = runner.invoke(app, ["get", "aws_instance.bastion"])

    assert result.exit_code == 1
    assert "No state loaded" in result.output


def test_get_missing_file_fails():
    result = runner.invoke(app, ["get", "/missing.json", "aws_instance.bastion"])

    assert result.exit_code == 1
    assert "Error" in result.output


def test_get_help():
    result = runner.invoke(app, ["get", "--help"])

    assert result.exit_code == 0
    assert "TARGET" in result.stdout
    assert "ADDRESS" in result.stdout
