import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.parser import parse_state_file
from tfstate.state_store import (
    clear_state,
    set_state,
    set_terraform_mode,
)
from tfstate.session import clear_session


runner = CliRunner()

BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"
BASIC_STATE_JSON = BASIC_FIXTURE.read_text()


@pytest.fixture(autouse=True)
def clean_state_before():
    clear_state()
    clear_session()


@pytest.fixture
def terraform_state(tmp_path):
    state = parse_state_file(BASIC_FIXTURE)
    set_state(state, str(BASIC_FIXTURE), "local")
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    set_terraform_mode(str(ws_dir), {"backend": "local"})
    return state, str(ws_dir)


def state_without(address: str) -> str:
    data = json.loads(BASIC_STATE_JSON)
    data["resources"] = [
        r
        for r in data["resources"]
        if _resource_address(r) != address
    ]
    return json.dumps(data)


def _resource_address(resource: dict) -> str:
    parts = []
    if resource.get("module"):
        parts.append(resource["module"])
    parts.append(resource.get("type", ""))
    parts.append(resource.get("name", ""))
    return ".".join(parts)


class TestRmHelp:
    def test_rm_help_shows_options(self):
        result = runner.invoke(app, ["rm", "--help"])
        assert result.exit_code == 0
        assert "ADDRESS" in result.stdout
        assert "--yes" in result.stdout
        assert "-y" in result.stdout
        assert "--backup" in result.stdout
        assert "--debug" in result.stdout
        assert "--force" not in result.stdout


class TestRmErrors:
    def test_rm_without_any_init(self):
        result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

    def test_rm_without_terraform_mode(self, tmp_path):
        state = parse_state_file(BASIC_FIXTURE)
        set_state(state, str(BASIC_FIXTURE), "local")
        result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main"])
        assert result.exit_code == 1
        assert "terraform mode" in result.output

    def test_rm_address_not_found(self, terraform_state):
        with patch("subprocess.run"):
            result = runner.invoke(
                app, ["rm", "nonexistent.resource.foo", "--yes"]
            )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_rm_force_deprecated_alias(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("module.vpc.aws_vpc.main")

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--force"]
            )

        assert result.exit_code == 0
        assert "deprecated" in result.output.lower()
        assert "--yes" in result.output
        assert "Resource removed:" in result.stdout

    def test_rm_backup_failure_shows_error(self, terraform_state, tmp_path):
        state, _ = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        # Patch write_text to simulate a backup failure (e.g., unwritable path)
        with (
            patch("subprocess.run", return_value=mock_pull),
            patch("pathlib.Path.write_text", side_effect=OSError("read-only filesystem")),
        ):
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes"]
            )

        assert result.exit_code == 1
        assert "backup" in result.output.lower()
        assert "read-only filesystem" in result.output

    def test_rm_terraform_failure(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm_fail = MagicMock(returncode=1, stdout="", stderr="resource not found")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm_fail]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes"]
            )
        assert result.exit_code == 1
        assert "terraform state rm failed" in result.output
        assert "resource not found" in result.output

    def test_rm_terraform_pull_failure_is_non_fatal(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n",
            stderr="",
        )
        mock_pull_fail = MagicMock(returncode=1, stdout="", stderr="lock error")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_fail]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes"]
            )

        assert result.exit_code == 0
        assert "Resource removed:" in result.stdout
        assert "Warning" in result.stdout


class TestRmSuccess:
    def test_rm_basic_flow(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("module.vpc.aws_vpc.main")

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n"
                   "Successfully removed 1 resource instance(s).\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes"]
            )

        assert result.exit_code == 0
        assert "Resource removed: module.vpc.aws_vpc.main" in result.stdout
        assert "Backup:" in result.stdout
        assert "Resources remaining: 2" in result.stdout
        assert "Successfully removed 1 resource" in result.stdout

    def test_rm_with_confirmation(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("module.vpc.aws_vpc.main")

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n"
                   "Successfully removed 1 resource instance(s).\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main"], input="y\n"
            )

        assert result.exit_code == 0
        assert "Resource removed:" in result.stdout

    def test_rm_confirmation_cancelled(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run", return_value=mock_pull):
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main"], input="n\n"
            )

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output

    def test_rm_custom_backup_path(self, terraform_state, tmp_path):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("module.vpc.aws_vpc.main")
        custom_backup = tmp_path / "custom" / "backup.json"
        custom_backup.parent.mkdir(parents=True)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n"
                   "Successfully removed 1 resource instance(s).\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(
                app, [
                    "rm", "module.vpc.aws_vpc.main", "--yes",
                    "--backup", str(custom_backup),
                ]
            )

        assert result.exit_code == 0
        assert str(custom_backup) in result.stdout
        assert custom_backup.exists()
        assert json.loads(custom_backup.read_text())["version"] == 4


class TestRmNoBackup:
    def test_rm_no_backup_skips_backup_file(self, terraform_state):
        state, workspace = terraform_state
        updated_json = state_without("module.vpc.aws_vpc.main")
        backup_file = Path(workspace) / "terraform.tfstate.backup"

        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_rm, mock_pull_after]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--no-backup"]
            )

        assert result.exit_code == 0
        assert not backup_file.exists()
        assert "Resource removed:" in result.stdout

    def test_rm_no_backup_still_removes_resource(self, terraform_state):
        state, workspace = terraform_state
        updated_json = state_without("module.vpc.aws_vpc.main")

        mock_rm = MagicMock(
            returncode=0,
            stdout="Removed module.vpc.aws_vpc.main from state.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_rm, mock_pull_after]
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--no-backup"]
            )

        assert result.exit_code == 0
        assert "Resource removed: module.vpc.aws_vpc.main" in result.stdout

    def test_rm_no_backup_help_shows_flag(self):
        result = runner.invoke(app, ["rm", "--help"])
        assert result.exit_code == 0
        assert "--no-backup" in result.stdout


class TestRmDebug:
    def test_rm_debug_flag_shows_traceback(self, terraform_state):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected crash")):
            result = runner.invoke(
                app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--debug"]
            )

        assert result.exit_code == 1
        assert "Traceback" in result.output or "unexpected crash" in result.output
