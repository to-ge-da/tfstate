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
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["file"] == str(BASIC_FIXTURE)
        assert data["terraform_version"] == "1.5.7"
        assert data["serial"] == 42
        assert data["resources"]["total"] == 3
        assert "aws_vpc" in data["resources"]["by_type"]

    def test_show_plain(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "--format", "plain"])
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

        result = runner.invoke(app, ["show", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["terraform_version"] == "1.5.7"
        assert data["backend"] == "local"

    def test_show_plain_after_init(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["show", "--format", "plain"])
        assert result.exit_code == 0
        assert "Backend: local" in result.stdout


class TestFormatList:
    def test_list_json(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--format", "json"])
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
            app, ["list", str(BASIC_FIXTURE), "--type", "aws_instance", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0] == "aws_instance.bastion"

    def test_list_plain(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--format", "plain"])
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert "module.vpc.aws_vpc.main" in result.stdout
        assert "module.vpc.aws_subnet.public[0]" in result.stdout
        assert "module.vpc.aws_subnet.public[1]" in result.stdout
        assert "aws_instance.bastion" in result.stdout

    def test_list_plain_filtered(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "aws_vpc", "--format", "plain"]
        )
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "module.vpc.aws_vpc.main"

    def test_list_json_no_match(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "nonexistent", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_plain_no_match(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "nonexistent", "--format", "plain"]
        )
        assert result.exit_code == 0
        assert "No resources found with type: nonexistent" in result.stdout

    def test_list_rich_default(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout


class TestFormatPlacement:
    def test_format_after_command(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["terraform_version"] == "1.5.7"

    def test_format_short_flag_after_command(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["terraform_version"] == "1.5.7"

    def test_format_before_command_rejected(self):
        result = runner.invoke(app, ["--format", "json", "show", str(BASIC_FIXTURE)])
        assert result.exit_code != 0

    def test_invalid_format(self):
        result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "--format", "yaml"])
        assert result.exit_code != 0


class TestFormatInit:
    def test_init_json(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["source"] == str(BASIC_FIXTURE)
        assert data["terraform_version"] == "1.5.7"
        assert data["serial"] == 42
        assert data["resources"]["total"] == 3
        assert data["resources"]["instances"] == 4
        assert "aws_vpc" in data["resources"]["by_type"]

    def test_init_plain(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE), "--format", "plain"])
        assert result.exit_code == 0
        assert "Initialized state from" in result.stdout
        assert f"Source: {BASIC_FIXTURE}" in result.stdout
        assert "Terraform Version: 1.5.7" in result.stdout
        assert "Serial: 42" in result.stdout
        assert "Resources: 3 (4 instances)" in result.stdout
        assert "aws_vpc" in result.stdout
        assert "Outputs:" in result.stdout

    def test_init_rich_default(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0
        assert "Initialized state from" in result.stdout
        assert "1.5.7" in result.stdout


class TestFormatClear:
    def test_clear_json(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["clear", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "cleared"
        assert "deprecated" in result.stderr.lower()

    def test_clear_plain(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["clear", "--format", "plain"])
        assert result.exit_code == 0
        assert "Session cache cleared." in result.stdout

    def test_clear_rich_default(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout


class TestFormatCacheClear:
    def test_cache_clear_json(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["cache", "clear", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "cleared"
        assert "deprecated" not in result.output.lower()

    def test_cache_clear_plain(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["cache", "clear", "--format", "plain"])
        assert result.exit_code == 0
        assert "Session cache cleared." in result.stdout

    def test_cache_clear_rich_default(self):
        runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout


class TestDebugPlacement:
    def test_debug_after_command(self):
        from unittest.mock import patch

        with patch(
            "tfstate.commands.show.parse_state_file",
            side_effect=ValueError("unexpected crash"),
        ):
            result = runner.invoke(app, ["show", str(BASIC_FIXTURE), "--debug"])

        assert result.exit_code == 1
        assert "Traceback" in result.output
        assert "unexpected crash" in result.output
