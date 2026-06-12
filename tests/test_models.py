import pytest
from tfstate.parser import parse_state_data, StateParseError


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

    def test_get_nonexistent_resource(self, basic_state):
        result = basic_state.get_resource("nonexistent.resource")
        assert result is None