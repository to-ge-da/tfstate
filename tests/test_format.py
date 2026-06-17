import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.state_store import clear_state
from tfstate.session import clear_session


runner = CliRunner()


@pytest.fixture(autouse=True)
def clear_state_before():
    clear_state()
    clear_session()


BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"


class TestFormatShow:
    def test_show_json(self):
        result = runner.invoke(app, ["--format", "json", "show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["file"] == str(BASIC_FIXTURE)
        assert data["terraform_version"] == "1.5.7"
        assert data["serial"] == 42
        assert data["resources"]["total"] == 3
        assert "aws_vpc" in data["resources"]["by_type"]

    def test_show_plain(self):
        result = runner.invoke(app, ["--format", "plain", "show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "Terraform Version: 1.5.7" in result.stdout
        assert "Serial: 42" in result.stdout
        assert "Resources:" in result.stdout
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" in result.stdout
        assert "aws_instance" in result.stdout
        assert "Outputs:" in result.stdout
        assert "vpc_id" in result.stdout

    def test_show_rich_default(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "1.5.7" in result.stdout

    def test_show_json_after_init(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--format", "json", "show"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["terraform_version"] == "1.5.7"
        assert data["backend"] == "local"

    def test_show_plain_after_init(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--format", "plain", "show"])
        assert result.exit_code == 0
        assert "Backend: local" in result.stdout


class TestFormatList:
    def test_list_json(self):
        result = runner.invoke(app, ["--format", "json", "list", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 4
        assert "module.vpc.aws_vpc.main" in data
        assert "module.vpc.aws_subnet.public[0]" in data
        assert "module.vpc.aws_subnet.public[1]" in data
        assert "aws_instance.bastion" in data

    def test_list_json_filtered(self):
        result = runner.invoke(
            app, ["--format", "json", "list", str(BASIC_FIXTURE), "--type", "aws_instance"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0] == "aws_instance.bastion"

    def test_list_plain(self):
        result = runner.invoke(app, ["--format", "plain", "list", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert "module.vpc.aws_vpc.main" in result.stdout
        assert "module.vpc.aws_subnet.public[0]" in result.stdout
        assert "module.vpc.aws_subnet.public[1]" in result.stdout
        assert "aws_instance.bastion" in result.stdout

    def test_list_plain_filtered(self):
        result = runner.invoke(
            app, ["--format", "plain", "list", str(BASIC_FIXTURE), "--type", "aws_vpc"]
        )
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "module.vpc.aws_vpc.main"

    def test_list_json_no_match(self):
        result = runner.invoke(
            app, ["--format", "json", "list", str(BASIC_FIXTURE), "--type", "nonexistent"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_plain_no_match(self):
        result = runner.invoke(
            app, ["--format", "plain", "list", str(BASIC_FIXTURE), "--type", "nonexistent"]
        )
        assert result.exit_code == 0
        assert "No resources found with type: nonexistent" in result.stdout

    def test_list_rich_default(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout


class TestFormatGlobal:
    def test_format_before_command(self):
        result = runner.invoke(app, ["--format", "json", "show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["terraform_version"] == "1.5.7"

    def test_format_global_persists_across_commands(self):
        result = runner.invoke(app, ["--format", "json", "show", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "terraform_version" in data

    def test_invalid_format(self):
        result = runner.invoke(app, ["--format", "yaml", "show", str(BASIC_FIXTURE)])
        assert result.exit_code != 0
