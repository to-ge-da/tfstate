import json
from pathlib import Path
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.models import State, Resource, Instance
from tfstate.session import save_session, load_session, clear_session, SESSION_DIR, SESSION_FILE, STATE_FILE
from tfstate.state_store import clear_state


runner = CliRunner()
BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"


def make_test_state() -> State:
    return State(
        version=4,
        terraform_version="1.5.7",
        serial=42,
        lineage="test-lineage",
        outputs={},
        resources=[
            Resource(
                module=None,
                mode="managed",
                type="aws_instance",
                name="test",
                provider="provider[\"registry.terraform.io/hashicorp/aws\"]",
                instances=[
                    Instance(
                        schema_version=1,
                        attributes={"id": "i-123", "instance_type": "t2.micro"},
                        dependencies=[],
                    )
                ],
            )
        ],
    )


class TestSessionSaveLoad:
    def test_save_and_load_round_trip(self):
        state = make_test_state()
        save_session(state, "s3://bucket/key", backend="S3", terraform_mode=True, workspace="/tmp/ws")

        assert SESSION_FILE.exists()
        assert STATE_FILE.exists()

        result = load_session()
        assert result is not None
        loaded_state, source, backend, terraform_mode, workspace = result

        assert loaded_state.terraform_version == "1.5.7"
        assert loaded_state.serial == 42
        assert len(loaded_state.resources) == 1
        assert loaded_state.resources[0].type == "aws_instance"
        assert source == "s3://bucket/key"
        assert backend == "S3"
        assert terraform_mode is True
        assert workspace == "/tmp/ws"

    def test_save_without_backend(self):
        state = make_test_state()
        save_session(state, "/path/to/file.json")

        result = load_session()
        assert result is not None
        _, source, backend, terraform_mode, _ = result
        assert source == "/path/to/file.json"
        assert backend is None
        assert terraform_mode is False

    def test_load_returns_none_when_no_cache(self):
        clear_session()
        assert load_session() is None

    def test_load_returns_none_on_corrupt_json(self):
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text("not valid json")
        SESSION_FILE.write_text("not valid json")
        assert load_session() is None

    def test_clear_session_removes_cache(self):
        state = make_test_state()
        save_session(state, "s3://bucket/key")
        assert SESSION_DIR.exists()

        clear_session()
        assert not SESSION_DIR.exists()
        assert load_session() is None


class TestShowListFromCache:
    def test_show_uses_cache_when_no_in_memory_state(self, tmp_path: Path):
        import tfstate.session as s

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        s.SESSION_DIR = fake_home / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        state_data = BASIC_FIXTURE.read_text()
        s.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        s.STATE_FILE.write_text(state_data)
        s.SESSION_FILE.write_text(json.dumps({
            "source": str(BASIC_FIXTURE),
            "backend": "local",
            "terraform_mode": False,
            "workspace": None,
            "cached_at": "2026-06-16T12:00:00",
        }))

        clear_state()

        result = runner.invoke(app, ["show"])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "1.5.7" in result.stdout
        assert "Resources:" in result.stdout

        s.SESSION_DIR = Path.home() / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

    def test_list_uses_cache_when_no_in_memory_state(self, tmp_path: Path):
        import tfstate.session as s

        fake_home = tmp_path / "home2"
        fake_home.mkdir()

        s.SESSION_DIR = fake_home / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        state_data = BASIC_FIXTURE.read_text()
        s.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        s.STATE_FILE.write_text(state_data)
        s.SESSION_FILE.write_text(json.dumps({
            "source": str(BASIC_FIXTURE),
            "backend": "local",
            "terraform_mode": False,
            "workspace": None,
            "cached_at": "2026-06-16T12:00:00",
        }))

        clear_state()

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout

        s.SESSION_DIR = Path.home() / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

    def test_show_errors_without_cache_and_without_init(self):
        clear_state()
        clear_session()

        import tfstate.session as s
        original_dir = s.SESSION_DIR
        s.SESSION_DIR = Path("/nonexistent") / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        result = runner.invoke(app, ["show"])
        assert result.exit_code == 1
        assert "No state loaded" in result.output

        s.SESSION_DIR = original_dir
        s.SESSION_FILE = original_dir / "session.json"
        s.STATE_FILE = original_dir / "state.json"

    def test_init_then_fresh_process_then_show(self, tmp_path: Path):
        import tfstate.session as s

        fake_home = tmp_path / "fresh"
        fake_home.mkdir()

        s.SESSION_DIR = fake_home / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        state_data = BASIC_FIXTURE.read_text()
        s.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        s.STATE_FILE.write_text(state_data)
        s.SESSION_FILE.write_text(json.dumps({
            "source": str(BASIC_FIXTURE),
            "backend": "local",
            "terraform_mode": False,
            "workspace": None,
            "cached_at": "2026-06-16T12:00:00",
        }))

        clear_state()

        result = runner.invoke(app, ["show"])
        assert result.exit_code == 0
        assert "State File:" in result.stdout
        assert "Resources:" in result.stdout
        assert "aws_vpc" in result.stdout

        s.SESSION_DIR = Path.home() / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

    def test_list_type_filter_from_cache(self, tmp_path: Path):
        import tfstate.session as s

        fake_home = tmp_path / "type-filter"
        fake_home.mkdir()

        s.SESSION_DIR = fake_home / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        state_data = BASIC_FIXTURE.read_text()
        s.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        s.STATE_FILE.write_text(state_data)
        s.SESSION_FILE.write_text(json.dumps({
            "source": str(BASIC_FIXTURE),
            "backend": "local",
            "terraform_mode": False,
            "workspace": None,
            "cached_at": "2026-06-16T12:00:00",
        }))

        clear_state()

        result = runner.invoke(app, ["list", "--type", "aws_vpc"])
        assert result.exit_code == 0
        assert "aws_vpc" in result.stdout
        assert "aws_subnet" not in result.stdout
        assert "aws_instance" not in result.stdout

        s.SESSION_DIR = Path.home() / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

    def test_list_module_filter_from_cache(self, tmp_path: Path):
        import tfstate.session as s

        fake_home = tmp_path / "module-filter"
        fake_home.mkdir()

        s.SESSION_DIR = fake_home / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"

        state_data = BASIC_FIXTURE.read_text()
        s.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        s.STATE_FILE.write_text(state_data)
        s.SESSION_FILE.write_text(json.dumps({
            "source": str(BASIC_FIXTURE),
            "backend": "local",
            "terraform_mode": False,
            "workspace": None,
            "cached_at": "2026-06-16T12:00:00",
        }))

        clear_state()

        result = runner.invoke(app, ["list", "--module", "module.vpc"])
        assert result.exit_code == 0
        assert "module.vpc" in result.stdout
        assert "aws_instance" not in result.stdout  # root module resource

        s.SESSION_DIR = Path.home() / ".tfstate"
        s.SESSION_FILE = s.SESSION_DIR / "session.json"
        s.STATE_FILE = s.SESSION_DIR / "state.json"


class TestClearCommand:
    def test_clear_command_removes_cache(self, tmp_path: Path):
        state = make_test_state()
        save_session(state, "s3://bucket/key")
        assert SESSION_DIR.exists()

        result = runner.invoke(app, ["clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout
        assert not SESSION_DIR.exists()
        assert "deprecated" in result.stderr.lower()
        assert "cache clear" in result.stderr

    def test_clear_command_when_no_cache(self):
        clear_session()

        result = runner.invoke(app, ["clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout
        assert "deprecated" in result.stderr.lower()
        assert "cache clear" in result.stderr


class TestCacheClearCommand:
    def test_cache_clear_removes_cache(self):
        state = make_test_state()
        save_session(state, "s3://bucket/key")
        assert SESSION_DIR.exists()

        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout
        assert not SESSION_DIR.exists()
        assert "deprecated" not in result.output.lower()

    def test_cache_clear_when_no_cache(self):
        clear_session()

        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "Session cache cleared" in result.stdout
        assert "deprecated" not in result.output.lower()

    def test_cache_clear_json(self):
        state = make_test_state()
        save_session(state, "s3://bucket/key")

        result = runner.invoke(app, ["cache", "clear", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "cleared"
        assert not SESSION_DIR.exists()
