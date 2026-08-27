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
    data["resources"] = [r for r in data["resources"] if _resource_address(r) != address]
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
        assert "--interactive" in result.stdout
        assert "-i" in result.stdout
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
            result = runner.invoke(app, ["rm", "nonexistent.resource.foo", "--yes"])
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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--force"])

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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes"])

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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes"])
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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes"])

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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes"])

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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main"], input="y\n")

        assert result.exit_code == 0
        assert "Resource removed:" in result.stdout

    def test_rm_confirmation_cancelled(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run", return_value=mock_pull):
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main"], input="n\n")

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
                app,
                [
                    "rm",
                    "module.vpc.aws_vpc.main",
                    "--yes",
                    "--backup",
                    str(custom_backup),
                ],
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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--no-backup"])

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
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--no-backup"])

        assert result.exit_code == 0
        assert "Resource removed: module.vpc.aws_vpc.main" in result.stdout

    def test_rm_no_backup_help_shows_flag(self):
        result = runner.invoke(app, ["rm", "--help"])
        assert result.exit_code == 0
        assert "--no-backup" in result.stdout


class TestRmDebug:
    def test_rm_debug_flag_shows_traceback(self, terraform_state):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected crash")):
            result = runner.invoke(app, ["rm", "module.vpc.aws_vpc.main", "--yes", "--debug"])

        assert result.exit_code == 1
        assert "Traceback" in result.output or "unexpected crash" in result.output


FOREACH_FIXTURE = Path(__file__).parent / "fixtures" / "foreach.json"


def _terraform_rm_cmd(mock_run) -> list[str] | None:
    for call in mock_run.call_args_list:
        cmd = call.args[0]
        if len(cmd) >= 3 and cmd[:3] == ["terraform", "state", "rm"]:
            return cmd
    return None


def _mock_checkbox(monkeypatch, selected, seen=None):
    def capture_checkbox(*args, **kwargs):
        if seen is not None:
            seen["choices"] = list(kwargs.get("choices", []))
            seen["kwargs"] = kwargs
        prompt = MagicMock()
        prompt.ask.return_value = selected
        return prompt

    monkeypatch.setattr("tfstate.commands.rm.questionary.checkbox", capture_checkbox)


class TestRmInteractive:
    def test_interactive_non_tty_exits_with_terminal_error(self, terraform_state):
        result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 1
        assert "interactive mode requires a terminal" in result.output

    def test_interactive_without_address_is_allowed_in_help(self):
        result = runner.invoke(app, ["rm", "--help"])
        assert result.exit_code == 0
        assert "--interactive" in result.stdout

    def test_rm_without_address_requires_interactive(self):
        result = runner.invoke(app, ["rm"])
        assert result.exit_code == 1
        assert "ADDRESS" in result.output
        assert "--interactive" in result.output

    def test_interactive_cannot_combine_with_address(self, terraform_state):
        result = runner.invoke(app, ["rm", "aws_instance.bastion", "--interactive"])
        assert result.exit_code == 1
        assert "cannot be combined" in result.output

    def test_interactive_without_any_init(self):
        result = runner.invoke(app, ["rm", "--interactive"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

    def test_interactive_without_terraform_mode(self):
        state = parse_state_file(BASIC_FIXTURE)
        set_state(state, str(BASIC_FIXTURE), "local")
        result = runner.invoke(app, ["rm", "--interactive"])
        assert result.exit_code == 1
        assert "terraform mode" in result.output

    def test_interactive_empty_state_exits_cleanly(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        state, _ = terraform_state
        state.resources.clear()

        with patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 0
        assert "No resources in state" in result.output
        mock_run.assert_not_called()

    def test_interactive_no_selection_leaves_state_untouched(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        _mock_checkbox(monkeypatch, [])

        with patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 0
        assert "No resources selected" in result.output
        mock_run.assert_not_called()

    def test_interactive_cancel_exits_130(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        _mock_checkbox(monkeypatch, None)

        with patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 130
        mock_run.assert_not_called()

    def test_interactive_keyboard_interrupt_exits_130(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)

        prompt = MagicMock()
        prompt.ask.side_effect = KeyboardInterrupt
        monkeypatch.setattr(
            "tfstate.commands.rm.questionary.checkbox",
            lambda *args, **kwargs: prompt,
        )

        with patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 130
        mock_run.assert_not_called()

    def test_interactive_term_dumb_errors(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: True)

        result = runner.invoke(app, ["rm", "--interactive"])

        assert result.exit_code == 1
        assert "TERM=dumb" in result.output

    def test_interactive_select_confirm_removes_selected(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        seen: dict = {}
        selected = ["module.vpc.aws_vpc.main", "aws_instance.bastion"]
        _mock_checkbox(monkeypatch, selected, seen=seen)

        state, _ = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("module.vpc.aws_vpc.main")

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0,
            stdout="Successfully removed 2 resource instance(s).\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(app, ["rm", "--interactive"], input="y\n")

        assert result.exit_code == 0
        assert seen["choices"] == [
            "module.vpc.aws_vpc.main",
            "module.vpc.aws_subnet.public[0]",
            "module.vpc.aws_subnet.public[1]",
            "aws_instance.bastion",
        ]
        assert "The following resources will be removed" in result.stdout
        assert "module.vpc.aws_vpc.main" in result.stdout
        assert "aws_instance.bastion" in result.stdout
        cmd = _terraform_rm_cmd(mock_run)
        assert cmd == ["terraform", "state", "rm", *selected]

    def test_interactive_yes_skips_confirm(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        selected = ["aws_instance.bastion"]
        _mock_checkbox(monkeypatch, selected)

        state, _ = terraform_state
        state_json = state.model_dump_json(indent=2)
        updated_json = state_without("aws_instance.bastion")

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0, stdout="Removed aws_instance.bastion from state.\n", stderr=""
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(app, ["rm", "--interactive", "--yes"])

        assert result.exit_code == 0
        assert "Resource removed: aws_instance.bastion" in result.stdout
        assert _terraform_rm_cmd(mock_run) == ["terraform", "state", "rm", "aws_instance.bastion"]

    def test_interactive_confirmation_cancelled(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        _mock_checkbox(monkeypatch, ["aws_instance.bastion"])

        with patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["rm", "--interactive"], input="n\n")

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output
        mock_run.assert_not_called()

    def test_interactive_foreach_addresses_use_index_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        state = parse_state_file(FOREACH_FIXTURE)
        set_state(state, str(FOREACH_FIXTURE), "local")
        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir(parents=True, exist_ok=True)
        set_terraform_mode(str(ws_dir), {"backend": "local"})

        seen: dict = {}
        selected = ['aws_s3_bucket.logs["logs"]', "aws_instance.web[0]"]
        _mock_checkbox(monkeypatch, selected, seen=seen)

        state_json = state.model_dump_json(indent=2)
        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_rm = MagicMock(
            returncode=0, stdout="Successfully removed 2 resource instance(s).\n", stderr=""
        )
        mock_pull_after = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_rm, mock_pull_after]
            result = runner.invoke(app, ["rm", "--interactive", "--yes"])

        assert result.exit_code == 0
        assert seen["choices"] == [
            'aws_s3_bucket.logs["logs"]',
            'aws_s3_bucket.logs["backups"]',
            "aws_instance.web[0]",
            "aws_instance.web[1]",
        ]
        assert _terraform_rm_cmd(mock_run) == ["terraform", "state", "rm", *selected]
        assert 'aws_s3_bucket.logs["logs"]' in result.stdout
        assert "aws_instance.web[0]" in result.stdout

    def test_interactive_no_backup(self, terraform_state, monkeypatch):
        monkeypatch.setattr("tfstate.commands.rm._is_tty", lambda: True)
        monkeypatch.setattr("tfstate.commands.rm._is_dumb_term", lambda: False)
        _mock_checkbox(monkeypatch, ["aws_instance.bastion"])

        state, workspace = terraform_state
        updated_json = state_without("aws_instance.bastion")
        backup_file = Path(workspace) / "terraform.tfstate.backup"

        mock_rm = MagicMock(
            returncode=0, stdout="Removed aws_instance.bastion from state.\n", stderr=""
        )
        mock_pull_after = MagicMock(returncode=0, stdout=updated_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_rm, mock_pull_after]
            result = runner.invoke(app, ["rm", "--interactive", "--yes", "--no-backup"])

        assert result.exit_code == 0
        assert not backup_file.exists()
        assert _terraform_rm_cmd(mock_run) == ["terraform", "state", "rm", "aws_instance.bastion"]
