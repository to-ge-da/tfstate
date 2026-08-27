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

    def test_list_filter_by_type_no_match(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--type", "nonexistent"])
        assert result.exit_code == 0
        assert "No resources found with type: nonexistent" in result.stdout
        assert "Available types in state" in result.stdout
        assert "aws_vpc" in result.stdout

    def test_list_filter_by_type_typo(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--type", "aws_instanc"])
        assert result.exit_code == 0
        assert "No resources found with type: aws_instanc" in result.stdout
        assert "Did you mean:" in result.stdout
        assert "aws_instance" in result.stdout
        assert "Available types" not in result.stdout

    def test_list_filter_by_type_typo_combined(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "aws_instanc", "--module", "module.vpc"]
        )
        assert result.exit_code == 0
        assert "Did you mean:" in result.stdout
        assert "aws_instance" in result.stdout

    def test_list_filter_by_module_no_match(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--module", "nonexistent"])
        assert result.exit_code == 0
        assert "No resources found with module: nonexistent" in result.stdout
        assert "Available modules in state" in result.stdout
        assert "module.vpc" in result.stdout

    def test_list_filter_by_module_typo(self):
        result = runner.invoke(app, ["list", str(BASIC_FIXTURE), "--module", "module.vp"])
        assert result.exit_code == 0
        assert "No resources found with module: module.vp" in result.stdout
        assert "Did you mean:" in result.stdout
        assert "module.vpc" in result.stdout
        assert "Available modules" not in result.stdout

    def test_list_filter_by_type_no_match_connected(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["list", "--type", "nonexistent"])
        assert result.exit_code == 0
        assert "No resources found" in result.stdout
        assert "Available types in state" in result.stdout
        assert "aws_vpc" in result.stdout

    def test_list_filter_by_module_no_match_connected(self):
        result = runner.invoke(app, ["init", str(BASIC_FIXTURE)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["list", "--module", "nonexistent"])
        assert result.exit_code == 0
        assert "No resources found" in result.stdout
        assert "Available modules in state" in result.stdout
        assert "module.vpc" in result.stdout

    def test_list_filter_combined_no_match(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "aws_vpc", "--module", "nonexistent"]
        )
        assert result.exit_code == 0
        assert "No resources found" in result.stdout

    def test_list_filter_combined_correct_type_bad_module(self):
        result = runner.invoke(
            app, ["list", str(BASIC_FIXTURE), "--type", "aws_vpc", "--module", "nonexistent"]
        )
        assert result.exit_code == 0
        assert "Available types in state" in result.stdout
        assert "Available modules in state" in result.stdout

    def test_list_offline_file_not_found(self):
        result = runner.invoke(app, ["list", "/nonexistent/path.json"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestShowListHelp:
    def test_root_help_describes_all_commands(self):
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        descriptions = {
            "init": "Initialize state from a local file or S3 backend.",
            "show": "Show state metadata and resource summary.",
            "list": "List resources in state.",
            "get": "Show detailed information about a resource.",
            "query": "Explore resources interactively, or filter them non-interactively.",
            "diff": "Compare two state files.",
            "pull": "Download state from S3.",
            "mv": "Move a resource to a new address.",
            "rm": "Remove a resource from connected state.",
            "cache": "Manage session and workspace cache",
            "clear": "Clear cached session state",
        }
        help_text = " ".join(
            "".join(ch if ch.isascii() else " " for ch in result.stdout).split()
        )
        for command, description in descriptions.items():
            assert command in result.stdout
            assert description in help_text
        assert "deprecated" in result.stdout.lower()

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
        assert "--show-all-types" in result.stdout

    def test_cache_help_lists_clear(self):
        result = runner.invoke(app, ["cache", "--help"])
        assert result.exit_code == 0
        assert "clear" in result.stdout
        assert "Clear cached session state" in result.stdout

    def test_clear_help_marked_deprecated(self):
        result = runner.invoke(app, ["clear", "--help"])
        assert result.exit_code == 0
        assert "deprecated" in result.stdout.lower()
        assert "cache clear" in result.stdout
