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


def _resource_address(resource: dict) -> str:
    parts = []
    if resource.get("module"):
        parts.append(resource["module"])
    parts.append(resource.get("type", ""))
    parts.append(resource.get("name", ""))
    return ".".join(parts)


class TestMvHelp:
    def test_mv_help_shows_options(self):
        result = runner.invoke(app, ["mv", "--help"])
        assert result.exit_code == 0
        assert "SRC" in result.stdout
        assert "DST" in result.stdout
        assert "--yes" in result.stdout
        assert "-y" in result.stdout
        assert "--backup" in result.stdout
        assert "--debug" in result.stdout
        assert "--force" not in result.stdout


class TestMvErrors:
    def test_mv_without_any_init(self):
        result = runner.invoke(app, ["mv", "module.vpc.aws_vpc.main", "module.vpc.aws_vpc.moved"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

    def test_mv_without_terraform_mode(self, tmp_path):
        state = parse_state_file(BASIC_FIXTURE)
        set_state(state, str(BASIC_FIXTURE), "local")
        result = runner.invoke(
            app, ["mv", "module.vpc.aws_vpc.main", "module.vpc.aws_vpc.moved"]
        )
        assert result.exit_code == 1
        assert "terraform mode" in result.output

    def test_mv_src_not_found(self, terraform_state):
        with patch("subprocess.run"):
            result = runner.invoke(
                app, ["mv", "nonexistent.resource.foo", "new.module.type.name", "--yes"]
            )
        assert result.exit_code == 1
        assert "Source resource not found" in result.output

    def test_mv_dst_already_exists(self, terraform_state):
        with patch("subprocess.run"):
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "aws_instance.bastion",
                    "--yes",
                ],
            )
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert "Refusing to overwrite" in result.output

    def test_mv_force_deprecated_alias(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv = MagicMock(
            returncode=0,
            stdout="Moved module.vpc.aws_vpc.main to module.vpc.aws_vpc.moved.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv, mock_pull_after]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        assert "deprecated" in result.output.lower()
        assert "--yes" in result.output
        assert "Resource moved:" in result.stdout

    def test_mv_backup_failure_shows_error(self, terraform_state, tmp_path):
        state, _ = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        with (
            patch("subprocess.run", return_value=mock_pull),
            patch("pathlib.Path.write_text", side_effect=OSError("read-only filesystem")),
        ):
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                ],
            )

        assert result.exit_code == 1
        assert "backup" in result.output.lower()
        assert "read-only filesystem" in result.output

    def test_mv_terraform_failure(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv_fail = MagicMock(returncode=1, stdout="", stderr="resource not found")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv_fail]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                ],
            )
        assert result.exit_code == 1
        assert "terraform state mv failed" in result.output
        assert "resource not found" in result.output

    def test_mv_state_refresh_failure_is_non_fatal(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv = MagicMock(
            returncode=0,
            stdout="Moved module.vpc.aws_vpc.main to module.vpc.aws_vpc.moved.\n",
            stderr="",
        )
        mock_pull_fail = MagicMock(returncode=1, stdout="", stderr="lock error")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv, mock_pull_fail]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                ],
            )

        assert result.exit_code == 0
        assert "Resource moved:" in result.stdout
        assert "Warning" in result.stdout


class TestMvSuccess:
    def test_mv_basic_flow(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv = MagicMock(
            returncode=0,
            stdout="Moved module.vpc.aws_vpc.main to module.vpc.aws_vpc.moved.\n"
                   "Successfully moved 1 resource(s).\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv, mock_pull_after]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                ],
            )

        assert result.exit_code == 0
        assert "Resource moved:" in result.stdout
        assert "module.vpc.aws_vpc.main" in result.stdout
        assert "module.vpc.aws_vpc.moved" in result.stdout
        assert "Backup:" in result.stdout
        assert "Successfully moved 1 resource" in result.stdout

    def test_mv_with_confirmation(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv = MagicMock(
            returncode=0,
            stdout="Moved module.vpc.aws_vpc.main to module.vpc.aws_vpc.moved.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv, mock_pull_after]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                ],
                input="y\n",
            )

        assert result.exit_code == 0
        assert "Resource moved:" in result.stdout

    def test_mv_confirmation_cancelled(self, terraform_state):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run", return_value=mock_pull):
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                ],
                input="n\n",
            )

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output

    def test_mv_custom_backup_path(self, terraform_state, tmp_path):
        state, workspace = terraform_state
        state_json = state.model_dump_json(indent=2)
        custom_backup = tmp_path / "custom" / "mv_backup.json"
        custom_backup.parent.mkdir(parents=True)

        mock_pull = MagicMock(returncode=0, stdout=state_json, stderr="")
        mock_mv = MagicMock(
            returncode=0,
            stdout="Moved module.vpc.aws_vpc.main to module.vpc.aws_vpc.moved.\n",
            stderr="",
        )
        mock_pull_after = MagicMock(returncode=0, stdout=state_json, stderr="")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_pull, mock_mv, mock_pull_after]
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                    "--backup",
                    str(custom_backup),
                ],
            )

        assert result.exit_code == 0
        assert str(custom_backup) in result.stdout
        assert custom_backup.exists()
        assert json.loads(custom_backup.read_text())["version"] == 4


class TestMvDebug:
    def test_mv_debug_flag_shows_traceback(self, terraform_state):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected crash")):
            result = runner.invoke(
                app,
                [
                    "mv",
                    "module.vpc.aws_vpc.main",
                    "module.vpc.aws_vpc.moved",
                    "--yes",
                    "--debug",
                ],
            )

        assert result.exit_code == 1
        assert "Traceback" in result.output or "unexpected crash" in result.output
