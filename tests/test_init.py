import pytest
from pathlib import Path
from typer.testing import CliRunner

from tfstate.commands.init import is_s3_uri, parse_s3_uri
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
        assert "--debug" in result.stdout
