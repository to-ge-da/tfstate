import json
from pathlib import Path

from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.parser import parse_state_file
from tfstate.session import clear_session
from tfstate.state_store import clear_state

runner = CliRunner()
BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"
NESTED_FIXTURE = Path(__file__).parent / "fixtures" / "nested_modules.json"
FOREACH_FIXTURE = Path(__file__).parent / "fixtures" / "foreach.json"


def _addresses(state) -> list[str]:
    return [
        resource.full_address(i)
        for resource in state.resources
        for i in range(len(resource.instances))
    ]


def _invoke_filter(state_file: Path, output: Path, *flags: str):
    return runner.invoke(app, ["filter", str(state_file), "--output", str(output), *flags])


class TestFilterCommand:
    def setup_method(self):
        clear_state()
        clear_session()

    def test_include_by_type(self, tmp_path):
        output = tmp_path / "instances.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--type", "aws_instance")

        assert result.exit_code == 0
        state = parse_state_file(output)
        assert _addresses(state) == ["aws_instance.bastion"]
        assert all(resource.type == "aws_instance" for resource in state.resources)

    def test_include_by_module(self, tmp_path):
        output = tmp_path / "vpc.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--module", "module.vpc")

        assert result.exit_code == 0
        state = parse_state_file(output)
        assert _addresses(state) == [
            "module.vpc.aws_vpc.main",
            "module.vpc.aws_subnet.public[0]",
            "module.vpc.aws_subnet.public[1]",
        ]

    def test_repeatable_types_are_or(self, tmp_path):
        output = tmp_path / "or.json"
        result = _invoke_filter(
            BASIC_FIXTURE, output, "--type", "aws_vpc", "--type", "aws_instance"
        )

        assert result.exit_code == 0
        assert set(_addresses(parse_state_file(output))) == {
            "module.vpc.aws_vpc.main",
            "aws_instance.bastion",
        }

    def test_type_and_module_are_and(self, tmp_path):
        output = tmp_path / "and.json"
        result = _invoke_filter(
            BASIC_FIXTURE, output, "--type", "aws_vpc", "--module", "module.vpc"
        )

        assert result.exit_code == 0
        assert _addresses(parse_state_file(output)) == ["module.vpc.aws_vpc.main"]

    def test_exclude_type_wins_over_include(self, tmp_path):
        output = tmp_path / "exclude.json"
        result = _invoke_filter(
            BASIC_FIXTURE,
            output,
            "--type",
            "aws_vpc",
            "--type",
            "aws_instance",
            "--exclude-type",
            "aws_vpc",
        )

        assert result.exit_code == 0
        assert _addresses(parse_state_file(output)) == ["aws_instance.bastion"]

    def test_exclude_module_wins_over_include(self, tmp_path):
        output = tmp_path / "exclude-mod.json"
        result = _invoke_filter(
            BASIC_FIXTURE, output, "--module", "module.vpc", "--exclude-module", "module.vpc"
        )

        assert result.exit_code == 0
        assert _addresses(parse_state_file(output)) == []

    def test_nested_module_includes_child_excludes_sibling(self, tmp_path):
        output = tmp_path / "nested.json"
        result = _invoke_filter(NESTED_FIXTURE, output, "--module", "module.vpc")

        assert result.exit_code == 0
        assert _addresses(parse_state_file(output)) == [
            "module.vpc.aws_vpc.main",
            "module.vpc.network.aws_route_table.public",
        ]

    def test_exclude_module_uses_prefix(self, tmp_path):
        output = tmp_path / "no-vpc2.json"
        result = _invoke_filter(NESTED_FIXTURE, output, "--exclude-module", "module.vpc2")

        assert result.exit_code == 0
        addresses = _addresses(parse_state_file(output))
        assert "module.vpc2.aws_vpc.other" not in addresses
        assert "module.vpc.aws_vpc.main" in addresses
        assert "module.vpc.network.aws_route_table.public" in addresses
        assert "aws_instance.bastion" in addresses

    def test_foreach_addresses_survive_type_filter(self, tmp_path):
        output = tmp_path / "buckets.json"
        result = _invoke_filter(FOREACH_FIXTURE, output, "--type", "aws_s3_bucket")

        assert result.exit_code == 0
        state = parse_state_file(output)
        assert _addresses(state) == [
            'aws_s3_bucket.logs["logs"]',
            'aws_s3_bucket.logs["backups"]',
        ]
        assert [inst.index_key for inst in state.resources[0].instances] == ["logs", "backups"]

    def test_count_index_keys_survive_type_filter(self, tmp_path):
        output = tmp_path / "web.json"
        result = _invoke_filter(FOREACH_FIXTURE, output, "--type", "aws_instance")

        assert result.exit_code == 0
        state = parse_state_file(output)
        assert _addresses(state) == ["aws_instance.web[0]", "aws_instance.web[1]"]
        assert [inst.index_key for inst in state.resources[0].instances] == [0, 1]

    def test_round_trip_parse(self, tmp_path):
        output = tmp_path / "roundtrip.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--module", "module.vpc")

        assert result.exit_code == 0
        parsed = json.loads(output.read_text())
        assert parsed["version"] == 4
        state = parse_state_file(output)
        assert state.version == 4
        assert len(state.resources) == 2

    def test_preserves_serial_lineage_version_and_outputs(self, tmp_path):
        output = tmp_path / "meta.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--type", "aws_instance")

        assert result.exit_code == 0
        state = parse_state_file(output)
        assert state.version == 4
        assert state.terraform_version == "1.5.7"
        assert state.serial == 42
        assert state.lineage == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert "vpc_id" in state.outputs
        assert state.outputs["vpc_id"].value == {"id": "vpc-0abc123def456"}

    def test_no_filters_copies_all_resources(self, tmp_path):
        output = tmp_path / "copy.json"
        result = _invoke_filter(BASIC_FIXTURE, output)

        assert result.exit_code == 0
        original = parse_state_file(BASIC_FIXTURE)
        copied = parse_state_file(output)
        assert _addresses(copied) == _addresses(original)

    def test_missing_output_flag_fails(self):
        result = runner.invoke(app, ["filter", str(BASIC_FIXTURE)])
        assert result.exit_code != 0

    def test_missing_state_file_fails(self, tmp_path):
        result = _invoke_filter(tmp_path / "missing.json", tmp_path / "out.json")
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_format_json_summary(self, tmp_path):
        output = tmp_path / "out.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--type", "aws_instance", "--format", "json")

        assert result.exit_code == 0
        summary = json.loads(result.stdout)
        assert summary["output"] == str(output)
        assert summary["resources"] == 1
        assert summary["instances"] == 1

    def test_format_plain_summary(self, tmp_path):
        output = tmp_path / "out.json"
        result = _invoke_filter(
            BASIC_FIXTURE, output, "--type", "aws_instance", "--format", "plain"
        )

        assert result.exit_code == 0
        assert str(output) in result.stdout
        assert "1" in result.stdout

    def test_debug_flag_accepted(self, tmp_path):
        output = tmp_path / "out.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--type", "aws_instance", "--debug")
        assert result.exit_code == 0

    def test_written_json_omits_null_index_key(self, tmp_path):
        output = tmp_path / "out.json"
        result = _invoke_filter(BASIC_FIXTURE, output, "--type", "aws_instance")

        assert result.exit_code == 0
        data = json.loads(output.read_text())
        instance = data["resources"][0]["instances"][0]
        assert "index_key" not in instance
        assert "name" not in data["outputs"]["vpc_id"]
