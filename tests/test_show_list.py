import pytest
from pathlib import Path
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.state_store import clear_state


runner = CliRunner()


@pytest.fixture(autouse=True)
def clear_state_before():
    clear_state()


BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"


class TestShowCommand:
    def test_show_offline(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "1.5.7" in result.stdout
        assert "Serial: 42" in result.stdout
        assert "Resources:" in result.stdout
        assert "aws_vpc" in result.stdout

    def test_show_without_init_and_without_file(self):
        result = runner.invoke(app, ["show"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

    def test_show_connected_after_init(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["show"])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "Backend:" in result.stdout
        assert "local" in result.stdout
        assert "1.5.7" in result.stdout
        assert "Resources:" in result.stdout

    def test_show_offline_file_not_found(self):
        result = runner.invoke(app, ["show", "/nonexistent/path.json"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestListCommand:
    def test_list_offline(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" in result.stdout
        assert "aws_instance" in result.stdout

    def test_list_without_init_and_without_file(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

    def test_list_connected_after_init(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" in result.stdout
        assert "aws_instance" in result.stdout

    def test_list_filter_by_type(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--type", "aws_instance"])
        assert result.exit_code == 0
        assert "aws_instance" in result.stdout
        assert "aws_vpc" not in result.stdout
        assert "aws_subnet" not in result.stdout

    def test_list_filter_by_type_connected(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["list", "--type", "aws_vpc"])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" not in result.stdout

    def test_list_filter_by_module(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--module", "module.vpc"])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" in result.stdout
        assert "aws_instance" not in result.stdout

    def test_list_offline_file_not_found(self):
        result = runner.invoke(app, ["list", "/nonexistent/path.json"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestShowListHelp:
    def test_show_help(self):
        result = runner.invoke(app, ["show", "--help"])
        assert result.exit_code == 0
        assert "STATE_FILE" in result.stdout

    def test_list_help(self):
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "STATE_FILE" in result.stdout
        assert "--type" in result.stdout
        assert "--module" in result.stdout
