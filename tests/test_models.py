import pytest
from tfstate.parser import parse_state_data, StateParseError
from tfstate.models import Resource, Instance


class TestParseStateFile:
    def test_parses_valid_state_file(self, basic_state):
        assert basic_state.version == 4
        assert basic_state.terraform_version == "1.5.7"
        assert basic_state.serial == 42

    def test_parses_resources(self, basic_state):
        assert len(basic_state.resources) == 3

    def test_raises_on_missing_version(self):
        with pytest.raises(StateParseError, match="version"):
            parse_state_data({})

    def test_raises_on_unsupported_version(self):
        with pytest.raises(StateParseError, match="Unsupported state version"):
            parse_state_data({"version": 3})


class TestMatchesModule:
    def _resource(self, module: str | None) -> Resource:
        return Resource(
            module=module,
            type="aws_vpc",
            name="main",
            provider="provider[\"registry.terraform.io/hashicorp/aws\"]",
        )

    def test_exact_module(self):
        assert self._resource("module.vpc").matches_module("module.vpc")

    def test_child_module_prefix(self):
        assert self._resource("module.vpc.network").matches_module("module.vpc")

    def test_sibling_prefix_does_not_match(self):
        assert not self._resource("module.vpc2").matches_module("module.vpc")

    def test_root_module_does_not_match_named_prefix(self):
        assert not self._resource(None).matches_module("module.vpc")


class TestResourceAddress:
    def test_address_without_module(self, basic_state):
        instance = basic_state.resources[2]
        assert instance.address == "aws_instance.bastion"

    def test_address_with_module(self, basic_state):
        vpc = basic_state.resources[0]
        assert vpc.address == "module.vpc.aws_vpc.main"

    def test_full_address_with_multiple_instances(self, basic_state):
        subnet = basic_state.resources[1]
        assert subnet.full_address(0) == "module.vpc.aws_subnet.public[0]"
        assert subnet.full_address(1) == "module.vpc.aws_subnet.public[1]"


class TestResourcesByType:
    def test_groups_by_type(self, basic_state):
        by_type = basic_state.resources_by_type()
        assert "aws_vpc" in by_type
        assert "aws_subnet" in by_type
        assert "aws_instance" in by_type
        assert len(by_type["aws_subnet"]) == 1


class TestGetResource:
    def test_get_existing_resource(self, basic_state):
        result = basic_state.get_resource("module.vpc.aws_vpc.main")
        assert result is not None
        resource, idx = result
        assert resource.type == "aws_vpc"
        assert idx == 0

    def test_get_instance_by_index(self, basic_state):
        result = basic_state.get_resource("module.vpc.aws_subnet.public[0]")
        assert result is not None
        resource, idx = result
        assert resource.type == "aws_subnet"
        assert idx == 0

    def test_multi_instance_resource_requires_index(self, basic_state):
        result = basic_state.get_resource("module.vpc.aws_subnet.public")

        assert result is None

    def test_get_nonexistent_resource(self, basic_state):
        result = basic_state.get_resource("nonexistent.resource")
        assert result is None


class TestForEachAddresses:
    def test_string_index_key(self):
        state = parse_state_data(
            {
                "version": 4,
                "terraform_version": "1.5.7",
                "serial": 1,
                "lineage": "test",
                "resources": [
                    {
                        "mode": "managed",
                        "type": "aws_s3_bucket",
                        "name": "logs",
                        "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                        "instances": [
                            {
                                "schema_version": 0,
                                "attributes": {"id": "logs-bucket"},
                                "index_key": "logs",
                            },
                            {
                                "schema_version": 0,
                                "attributes": {"id": "backups-bucket"},
                                "index_key": "backups",
                            },
                        ],
                    }
                ],
            }
        )
        resource = state.resources[0]
        assert resource.full_address(0) == 'aws_s3_bucket.logs["logs"]'
        assert resource.full_address(1) == 'aws_s3_bucket.logs["backups"]'
        found, idx = state.get_resource('aws_s3_bucket.logs["backups"]')
        assert idx == 1
        assert found.instances[idx].attributes["id"] == "backups-bucket"
        assert state.get_resource("aws_s3_bucket.logs") is None

    def test_numeric_index_key_matches_count(self):
        resource = Resource(
            type="aws_instance",
            name="web",
            provider="provider[\"registry.terraform.io/hashicorp/aws\"]",
            instances=[
                Instance(schema_version=0, attributes={"id": "i-0"}, index_key=0),
                Instance(schema_version=0, attributes={"id": "i-1"}, index_key=1),
            ],
        )
        assert resource.full_address(0) == "aws_instance.web[0]"
        assert resource.full_address(1) == "aws_instance.web[1]"

