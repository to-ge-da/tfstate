import json
from pathlib import Path

from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.session import clear_session
from tfstate.state_store import clear_state

runner = CliRunner()
BASIC_FIXTURE = Path(__file__).parent / "fixtures" / "basic.json"
FOREACH_FIXTURE = Path(__file__).parent / "fixtures" / "foreach.json"


def setup_function():
    clear_state()
    clear_session()


def _graph(*args: str):
    return runner.invoke(app, ["graph", *args])


def _json_graph(*args: str) -> tuple[object, dict]:
    result = _graph(*args, "--format", "json")
    return result, json.loads(result.stdout) if result.exit_code == 0 else {}


def test_graph_forest_json():
    result, data = _json_graph(str(BASIC_FIXTURE))

    assert result.exit_code == 0
    assert [tree["address"] for tree in data["trees"]] == ["module.vpc.aws_vpc.main"]
    vpc = data["trees"][0]
    child_addrs = [child["address"] for child in vpc["dependents"]]
    assert child_addrs == [
        "module.vpc.aws_subnet.public[0]",
        "module.vpc.aws_subnet.public[1]",
        "aws_instance.bastion",
    ]
    subnet0 = vpc["dependents"][0]
    assert [child["address"] for child in subnet0["dependents"]] == ["aws_instance.bastion"]
    assert vpc["dependents"][1]["dependents"] == []
    assert data["cycles"] == []


def test_graph_forest_tree():
    result = _graph(str(BASIC_FIXTURE))

    assert result.exit_code == 0
    assert "module.vpc.aws_vpc.main" in result.stdout
    assert "module.vpc.aws_subnet.public[0]" in result.stdout
    assert "module.vpc.aws_subnet.public[1]" in result.stdout
    assert "aws_instance.bastion" in result.stdout
    assert "├──" in result.stdout or "└──" in result.stdout


def test_graph_address_subtree():
    result, data = _json_graph(
        str(BASIC_FIXTURE), "--address", "module.vpc.aws_subnet.public[0]"
    )

    assert result.exit_code == 0
    assert len(data["trees"]) == 1
    assert data["trees"][0]["address"] == "module.vpc.aws_subnet.public[0]"
    assert [child["address"] for child in data["trees"][0]["dependents"]] == [
        "aws_instance.bastion"
    ]


def test_graph_depth_limits_descendants():
    result, data = _json_graph(str(BASIC_FIXTURE), "--depth", "1")

    assert result.exit_code == 0
    vpc = data["trees"][0]
    assert vpc["address"] == "module.vpc.aws_vpc.main"
    child_addrs = [child["address"] for child in vpc["dependents"]]
    assert "module.vpc.aws_subnet.public[0]" in child_addrs
    assert "aws_instance.bastion" in child_addrs
    subnet0 = next(
        child for child in vpc["dependents"] if child["address"] == "module.vpc.aws_subnet.public[0]"
    )
    assert subnet0["dependents"] == []


def test_graph_depth_zero_is_roots_only():
    result, data = _json_graph(str(BASIC_FIXTURE), "--depth", "0")

    assert result.exit_code == 0
    assert data["trees"] == [
        {"address": "module.vpc.aws_vpc.main", "dependents": []},
    ]


def test_graph_dot_is_valid_graphviz():
    result = _graph(str(BASIC_FIXTURE), "--format", "dot")

    assert result.exit_code == 0
    stdout = result.stdout.strip()
    assert stdout.startswith("digraph tfstate {")
    assert stdout.endswith("}")
    assert "rankdir=TB;" in stdout
    assert '"module.vpc.aws_vpc.main" -> "module.vpc.aws_subnet.public[0]";' in stdout
    assert '"module.vpc.aws_vpc.main" -> "aws_instance.bastion";' in stdout
    assert (
        '"module.vpc.aws_subnet.public[0]" -> "aws_instance.bastion";' in stdout
    )


def test_graph_json_is_valid():
    result, data = _json_graph(str(BASIC_FIXTURE))

    assert result.exit_code == 0
    assert isinstance(data, dict)
    assert "trees" in data
    assert "cycles" in data
    json.dumps(data)


def test_graph_cycles_are_warned_and_truncated(tmp_path):
    cycle_file = tmp_path / "cycle.json"
    cycle_file.write_text(
        json.dumps(
            {
                "version": 4,
                "terraform_version": "1.5.7",
                "serial": 1,
                "lineage": "cycle",
                "outputs": {},
                "resources": [
                    {
                        "mode": "managed",
                        "type": "aws_a",
                        "name": "one",
                        "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                        "instances": [
                            {
                                "schema_version": 0,
                                "attributes": {"id": "a"},
                                "dependencies": ["aws_b.two"],
                            }
                        ],
                    },
                    {
                        "mode": "managed",
                        "type": "aws_b",
                        "name": "two",
                        "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                        "instances": [
                            {
                                "schema_version": 0,
                                "attributes": {"id": "b"},
                                "dependencies": ["aws_a.one"],
                            }
                        ],
                    },
                ],
            }
        )
    )

    result, data = _json_graph(str(cycle_file))

    assert result.exit_code == 0
    assert "Warning: cycle detected:" in result.output
    assert data["cycles"]
    assert all(cycle[0] == cycle[-1] for cycle in data["cycles"])

    def _has_cycle_flag(node: dict) -> bool:
        if node.get("cycle"):
            return True
        return any(_has_cycle_flag(child) for child in node.get("dependents", []))

    assert any(_has_cycle_flag(tree) for tree in data["trees"])


def test_graph_dot_quotes_foreach_keys():
    result = _graph(str(FOREACH_FIXTURE), "--format", "dot")

    assert result.exit_code == 0
    assert r'"aws_s3_bucket.logs[\"logs\"]";' in result.stdout
    assert r'"aws_s3_bucket.logs[\"backups\"]";' in result.stdout
    assert '"aws_instance.web[0]";' in result.stdout


def test_graph_unknown_address_suggests_match():
    result = _graph(str(BASIC_FIXTURE), "--address", "module.vpc.aws_vpc.mai")

    assert result.exit_code == 1
    assert "Resource not found" in result.output
    assert "Did you mean" in result.output
    assert "module.vpc.aws_vpc.main" in result.output


def test_graph_rejects_ambiguous_address():
    result = _graph(str(BASIC_FIXTURE), "--address", "module.vpc.aws_subnet.public")

    assert result.exit_code == 1
    assert "ambiguous" in result.output
    assert "module.vpc.aws_subnet.public[0]" in result.output


def test_graph_negative_depth_fails():
    result = _graph(str(BASIC_FIXTURE), "--depth", "-1")

    assert result.exit_code == 1
    assert "--depth must be >= 0" in result.output


def test_graph_without_state_fails():
    result = _graph()

    assert result.exit_code == 1
    assert "No state loaded" in result.output


def test_graph_connected_after_init():
    assert runner.invoke(app, ["init", str(BASIC_FIXTURE)]).exit_code == 0

    result, data = _json_graph()

    assert result.exit_code == 0
    assert data["trees"][0]["address"] == "module.vpc.aws_vpc.main"


def test_graph_help():
    result = runner.invoke(app, ["graph", "--help"])

    assert result.exit_code == 0
    assert "--address" in result.stdout
    assert "--depth" in result.stdout
    assert "tree" in result.stdout
    assert "dot" in result.stdout
    assert "json" in result.stdout
