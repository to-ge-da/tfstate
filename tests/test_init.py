import pytest
from pathlib import Path
from typer.testing import CliRunner

from tfstate.commands.init import (
    is_s3_uri,
    parse_s3_uri,
    generate_backend_tf,
    check_terraform_installed,
    resolve_workspace,
)
from tfstate.cli import app


runner = CliRunner()


class TestS3UriParsing:
    def test_is_s3_uri_valid(self):
        assert is_s3_uri("s3://bucket/key") is True
        assert is_s3_uri("s3://my-bucket/path/to/state.json") is True

    def test_is_s3_uri_invalid(self):
        assert is_s3_uri("./local/path.json") is False
        assert is_s3_uri("/absolute/path.json") is False
        assert is_s3_uri("https://bucket.s3.amazonaws.com/key") is False

    def test_parse_s3_uri_valid(self):
        bucket, key = parse_s3_uri("s3://my-bucket/path/to/terraform.tfstate")
        assert bucket == "my-bucket"
        assert key == "path/to/terraform.tfstate"

    def test_parse_s3_uri_root_key(self):
        bucket, key = parse_s3_uri("s3://bucket/state.json")
        assert bucket == "bucket"
        assert key == "state.json"

    def test_parse_s3_uri_invalid_scheme(self):
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            parse_s3_uri("https://bucket/key")

    def test_parse_s3_uri_missing_bucket(self):
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            parse_s3_uri("s3:///key")

    def test_parse_s3_uri_missing_key(self):
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            parse_s3_uri("s3://bucket")


class TestLocalFileInit:
    def test_init_local_file(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "basic.json"
        result = runner.invoke(app, ["init", str(fixture)])
        assert result.exit_code == 0
        assert "Initialized state from local backend" in result.stdout
        assert "1.5.7" in result.stdout
        assert "Serial: 42" in result.stdout
        assert "Resources: 3" in result.stdout

    def test_init_local_file_not_found(self):
        result = runner.invoke(app, ["init", "/nonexistent/path.json"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_init_invalid_json(self, tmp_path: Path):
        bad_file = tmp_path / "invalid.json"
        bad_file.write_text("not valid json")
        result = runner.invoke(app, ["init", str(bad_file)])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_init_unsupported_version(self, tmp_path: Path):
        state_content = '{"version": 3, "terraform_version": "1.0.0"}'
        state_file = tmp_path / "v3.json"
        state_file.write_text(state_content)
        result = runner.invoke(app, ["init", str(state_file)])
        assert result.exit_code == 1
        assert "Unsupported state version" in result.output


class TestInitCommandHelp:
    def test_help_shows_options(self):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.stdout
        assert "--region" in result.stdout
        assert "--terraform" in result.stdout
        assert "--output" in result.stdout
        assert "-o" in result.stdout


class TestInitOutputFlag:
    def test_local_init_with_output_creates_workspace(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "basic.json"
        ws_dir = tmp_path / "my-workspace"
        result = runner.invoke(app, ["init", str(fixture), "-o", str(ws_dir)])
        assert result.exit_code == 0
        assert ws_dir.is_dir()
        assert (ws_dir / "state.json").exists()
        assert "Workspace" in result.stdout

    def test_local_init_without_output_no_workspace(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "basic.json"
        result = runner.invoke(app, ["init", str(fixture)])
        assert result.exit_code == 0
        assert "Workspace" not in result.stdout

    def test_output_dir_non_empty_error(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "basic.json"
        ws_dir = tmp_path / "occupied"
        ws_dir.mkdir()
        (ws_dir / "dummy.txt").write_text("something")
        result = runner.invoke(app, ["init", str(fixture), "-o", str(ws_dir)])
        assert result.exit_code == 1
        assert "not empty" in result.output

    def test_output_parent_not_exists_error(self, tmp_path: Path):
        fixture = Path(__file__).parent / "fixtures" / "basic.json"
        result = runner.invoke(
            app, ["init", str(fixture), "-o", str(tmp_path / "nonexistent" / "child")]
        )
        assert result.exit_code == 1
        assert "Parent directory" in result.output


class TestResolveWorkspace:
    def test_creates_new_directory(self, tmp_path: Path):
        ws = tmp_path / "new-ws"
        path, reused = resolve_workspace(str(ws))
        assert ws.is_dir()
        assert reused is True

    def test_reuses_empty_directory(self, tmp_path: Path):
        ws = tmp_path / "empty-ws"
        ws.mkdir()
        path, reused = resolve_workspace(str(ws))
        assert ws.is_dir()
        assert reused is True

    def test_raises_on_non_empty_directory(self, tmp_path: Path):
        ws = tmp_path / "occupied"
        ws.mkdir()
        (ws / "file.txt").write_text("x")
        with pytest.raises(ValueError, match="not empty"):
            resolve_workspace(str(ws))

    def test_raises_on_missing_parent(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Parent directory"):
            resolve_workspace(str(tmp_path / "missing" / "child"))

    def test_no_output_returns_temp(self):
        path, reused = resolve_workspace(None)
        assert "tfstate-" in path
        assert reused is False


class TestTerraformBackend:
    def test_generate_backend_tf(self):
        content = generate_backend_tf(
            "my-bucket", "path/to/state.tfstate", "us-east-1", "my-profile"
        )
        assert 'bucket = "my-bucket"' in content
        assert 'key    = "path/to/state.tfstate"' in content
        assert 'region = "us-east-1"' in content
        assert 'profile = "my-profile"' in content
        assert 'backend "s3"' in content

    def test_generate_backend_tf_without_profile(self):
        content = generate_backend_tf("my-bucket", "path/to/state.tfstate", "us-east-1", None)
        assert 'bucket = "my-bucket"' in content
        assert 'profile = "my-profile"' not in content

    def test_check_terraform_installed(self):
        result = check_terraform_installed()
        assert isinstance(result, bool)
