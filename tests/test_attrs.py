import pytest

from tfstate.attrs import (
    format_attr_path,
    get_attr,
    is_missing,
    walk_attributes,
)


def test_get_attr_nested_mapping_and_list():
    attributes = {"rules": [{"port": 443}], "tags": {"Environment": "prod"}}

    assert get_attr(attributes, "tags.Environment") == "prod"
    assert get_attr(attributes, "rules[0].port") == 443


def test_get_attr_distinguishes_missing_from_null():
    attributes = {"present": None}

    assert get_attr(attributes, "present") is None
    assert is_missing(get_attr(attributes, "missing"))


@pytest.mark.parametrize("path", ["", ".tags", "tags.", "rules[x]", "rules[0]port"])
def test_invalid_attribute_paths(path):
    with pytest.raises(ValueError, match="attribute path"):
        get_attr({}, path)


def test_walk_attributes_preserves_empty_containers():
    values = dict(walk_attributes({"empty_dict": {}, "empty_list": [], "nested": [1]}))

    assert values[("empty_dict",)] == {}
    assert values[("empty_list",)] == []
    assert values[("nested", 0)] == 1
    assert format_attr_path(("nested", 0)) == "nested[0]"
