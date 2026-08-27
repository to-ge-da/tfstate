import json
from pathlib import Path

from typer.testing import CliRunner

from tfstate.cli import app
from tfstate.models import Resource
from tfstate.session import clear_session
from tfstate.state_store import clear_state

runner = CliRunner()
NESTED_FIXTURE = Path(__file__).parent / "fixtures" / "nested_modules.json"


class TestMatchesModule:
    def _resource(self, module: str | None) -> Resource:
        return Resource(
            module=module,
            type="aws_vpc",
            name="main",
            provider='provider["registry.terraform.io/hashicorp/aws"]',
        )

    def test_exact_module(self):
        assert self._resource("module.vpc").matches_module("module.vpc")

    def test_child_module_prefix(self):
        assert self._resource("module.vpc.network").matches_module("module.vpc")

    def test_sibling_prefix_does_not_match(self):
        assert not self._resource("module.vpc2").matches_module("module.vpc")

    def test_root_module_does_not_match_named_prefix(self):
        assert not self._resource(None).matches_module("module.vpc")


class TestListModulePrefix:
    def setup_method(self):
        clear_state()
        clear_session()

    def test_includes_children_excludes_siblings(self):
        result = runner.invoke(
            app, ["list", str(NESTED_FIXTURE), "--module", "module.vpc", "--format", "json"]
        )
        assert result.exit_code == 0
        addresses = json.loads(result.stdout)
        assert "module.vpc.aws_vpc.main" in addresses
        assert "module.vpc.network.aws_route_table.public" in addresses
        assert "module.vpc2.aws_vpc.other" not in addresses
        assert "aws_instance.bastion" not in addresses


class TestQueryModulePrefix:
    def setup_method(self):
        clear_state()
        clear_session()

    def test_includes_children_excludes_siblings(self):
        result = runner.invoke(
            app,
            ["query", str(NESTED_FIXTURE), "--module", "module.vpc", "--format", "json"],
        )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == [
            "module.vpc.aws_vpc.main",
            "module.vpc.network.aws_route_table.public",
        ]
