import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.session import clear_session
from tfstate.state_store import clear_state


runner = CliRunner()
BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"


@pytest.fixture(autouse=True)
def clear_loaded_state():
    clear_state()
    clear_session()


@pytest.fixture
def typed_fixture(tmp_path):
    data = json.loads(BASIC_FIXTURE.read_text())
    attributes = data["resources"][2]["instances"][0]["attributes"]
    attributes.update(
        {
            "enabled": True,
            "count": 3,
            "nullable": None,
            "ports": [80, 443],
            "tags": {"Environment": "prod", "Owner": "platform"},
        }
    )
    path = tmp_path / "typed.json"
    path.write_text(json.dumps(data))
    return path


def test_query_json_without_filters_returns_every_instance():
    result = runner.invoke(app, ["--format", "json", "query", str(BASIC_FIXTURE)])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        "module.vpc.aws_vpc.main",
        "module.vpc.aws_subnet.public[0]",
        "module.vpc.aws_subnet.public[1]",
        "aws_instance.bastion",
    ]


def test_bare_query_non_tty_rich_exits_with_migration_guidance():
    result = runner.invoke(app, ["query", str(BASIC_FIXTURE)])

    assert result.exit_code == 1
    assert "bare query requires a terminal" in result.output
    assert "tfstate list" in result.output
    assert "--interactive" in result.output


def test_interactive_non_tty_exits_with_terminal_error():
    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--interactive"])

    assert result.exit_code == 1
    assert "interactive mode requires a terminal" in result.output


@pytest.mark.parametrize("fmt", ["json", "plain"])
def test_interactive_incompatible_with_machine_formats(fmt):
    result = runner.invoke(app, ["--format", fmt, "query", str(BASIC_FIXTURE), "--interactive"])

    assert result.exit_code == 1
    assert "--interactive cannot be used with --format" in result.output


def test_interactive_success_shows_get_output(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    prompt = MagicMock()
    prompt.ask.return_value = "aws_instance.bastion"
    seen_kwargs = {}

    def capture_select(*args, **kwargs):
        seen_kwargs.update(kwargs)
        return prompt

    monkeypatch.setattr("tfstate.commands.query.questionary.select", capture_select)

    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--interactive"])

    assert result.exit_code == 0
    assert "Resource:" in result.stdout
    assert "aws_instance.bastion" in result.stdout
    assert "instance_type" in result.stdout
    assert seen_kwargs["pointer"] == "➜"
    assert seen_kwargs["style"] is not None
    prompt.ask.assert_called_once()


def test_interactive_cancel_exits_130(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    prompt = MagicMock()
    prompt.ask.return_value = None
    monkeypatch.setattr(
        "tfstate.commands.query.questionary.select",
        lambda *args, **kwargs: prompt,
    )

    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--interactive"])

    assert result.exit_code == 130


def test_interactive_keyboard_interrupt_exits_130(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    prompt = MagicMock()
    prompt.ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(
        "tfstate.commands.query.questionary.select",
        lambda *args, **kwargs: prompt,
    )

    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--interactive"])

    assert result.exit_code == 130


def test_one_candidate_auto_selects_without_prompt(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("select should not be called for one candidate")

    monkeypatch.setattr(
        "tfstate.commands.query.questionary.select",
        fail_if_called,
    )

    result = runner.invoke(
        app,
        ["query", str(BASIC_FIXTURE), "--interactive", "--type", "aws_instance"],
    )

    assert result.exit_code == 0
    assert not called
    assert "aws_instance.bastion" in result.stdout
    assert "Resource:" in result.stdout


def test_interactive_empty_candidates_message(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    result = runner.invoke(
        app,
        ["query", str(BASIC_FIXTURE), "--interactive", "--type", "nonexistent"],
    )

    assert result.exit_code == 0
    assert "No matching resources found" in result.stdout


def test_interactive_with_filter_narrows_candidates(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: False)

    seen_choices = []
    seen_kwargs = {}

    def capture_select(*args, **kwargs):
        seen_choices.extend(kwargs.get("choices", []))
        seen_kwargs.update(kwargs)
        prompt = MagicMock()
        prompt.ask.return_value = "module.vpc.aws_vpc.main"
        return prompt

    monkeypatch.setattr(
        "tfstate.commands.query.questionary.select",
        capture_select,
    )

    result = runner.invoke(
        app,
        ["query", str(BASIC_FIXTURE), "--interactive", "--module", "module.vpc"],
    )

    assert result.exit_code == 0
    assert seen_choices == [
        "module.vpc.aws_vpc.main",
        "module.vpc.aws_subnet.public[0]",
        "module.vpc.aws_subnet.public[1]",
    ]
    assert seen_kwargs["pointer"] == "➜"
    assert seen_kwargs["style"] is not None
    assert "module.vpc.aws_vpc.main" in result.stdout


def test_term_dumb_falls_back_to_non_interactive(monkeypatch):
    monkeypatch.setattr("tfstate.commands.query._is_tty", lambda: True)
    monkeypatch.setattr("tfstate.commands.query._is_dumb_term", lambda: True)

    result = runner.invoke(app, ["query", str(BASIC_FIXTURE)])

    assert result.exit_code == 0
    assert "TERM=dumb" in result.output
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "aws_instance.bastion" in result.stdout


def test_query_filters_by_type_and_module_with_and_semantics():
    result = runner.invoke(
        app,
        [
            "query",
            str(BASIC_FIXTURE),
            "--type",
            "aws_vpc",
            "--module",
            "module.vpc",
        ],
    )

    assert result.exit_code == 0
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "aws_subnet" not in result.stdout


def test_query_repeatable_attributes_and_typed_values(typed_fixture):
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--attr",
            "tags.Environment=prod",
            "--attr",
            "enabled=true",
            "--attr",
            "count=3",
            "--attr",
            "ports=[80, 443]",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == ["aws_instance.bastion"]


def test_query_has_and_missing_attributes_distinguish_null(typed_fixture):
    present = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--has-attr",
            "nullable",
            "--has-attr",
            "tags.Owner",
        ],
    )
    missing = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--missing-attr",
            "tags.CostCenter",
            "--type",
            "aws_instance",
        ],
    )

    assert present.exit_code == 0
    assert json.loads(present.stdout) == ["aws_instance.bastion"]
    assert missing.exit_code == 0
    assert json.loads(missing.stdout) == ["aws_instance.bastion"]


def test_query_list_index_path(typed_fixture):
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "query",
            str(typed_fixture),
            "--attr",
            "ports[1]=443",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == ["aws_instance.bastion"]


def test_query_no_match_contracts():
    rich = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--type", "nonexistent"])
    plain = runner.invoke(
        app,
        ["--format", "plain", "query", str(BASIC_FIXTURE), "--type", "nonexistent"],
    )
    json_result = runner.invoke(
        app,
        ["--format", "json", "query", str(BASIC_FIXTURE), "--type", "nonexistent"],
    )

    assert rich.exit_code == plain.exit_code == json_result.exit_code == 0
    assert "No matching resources found" in rich.stdout
    assert "No matching resources found" in plain.stdout
    assert json.loads(json_result.stdout) == []


@pytest.mark.parametrize("expression", ["invalid", "=value", "tags."])
def test_query_rejects_malformed_attr_filter(expression):
    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--attr", expression])

    assert result.exit_code == 2
    assert "--attr" in result.output


def test_query_rejects_invalid_presence_path():
    result = runner.invoke(app, ["query", str(BASIC_FIXTURE), "--has-attr", "rules[x]"])

    assert result.exit_code == 2
    assert "--has-attr" in result.output


def test_query_connected_after_init():
    assert runner.invoke(app, ["init", str(BASIC_FIXTURE)]).exit_code == 0

    result = runner.invoke(app, ["query", "--type", "aws_instance"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "aws_instance.bastion"


def test_query_without_loaded_state_fails():
    result = runner.invoke(app, ["query", "--type", "aws_instance"])

    assert result.exit_code == 1
    assert "No state loaded" in result.output


def test_query_help():
    result = runner.invoke(app, ["query", "--help"])

    assert result.exit_code == 0
    assert "STATE_FILE" in result.stdout
    assert "--type" in result.stdout
    assert "--module" in result.stdout
    assert "--attr" in result.stdout
    assert "--has-attr" in result.stdout
    assert "--missing-attr" in result.stdout
    assert "--interactive" in result.stdout
