from pathlib import Path
from typing import Any

from tfstate import debug
from tfstate.attrs import format_attr_path
from tfstate.models import Instance, Resource, State
from tfstate.output import print_diff
from tfstate.parser import StateParseError, parse_state_file


_MISSING = object()


def diff(file1: Path, file2: Path) -> None:
    try:
        old_state = parse_state_file(file1)
        new_state = parse_state_file(file2)
    except StateParseError as e:
        debug.exit_with_traceback(e)
        return
    except Exception as e:
        debug.exit_with_traceback(e)
        return

    print_diff(compare_states(old_state, new_state))


def compare_states(old_state: State, new_state: State) -> dict[str, Any]:
    old_instances = _index_instances(old_state)
    new_instances = _index_instances(new_state)

    removed = [
        {"address": address, "type": resource.type}
        for address, (resource, _) in old_instances.items()
        if address not in new_instances
    ]
    added = [
        {"address": address, "type": resource.type}
        for address, (resource, _) in new_instances.items()
        if address not in old_instances
    ]

    modified = []
    for address, (old_resource, old_instance) in old_instances.items():
        if address not in new_instances:
            continue
        _, new_instance = new_instances[address]
        changes = _compare_values(old_instance.attributes, new_instance.attributes)
        if changes:
            modified.append(
                {
                    "address": address,
                    "type": old_resource.type,
                    "changes": changes,
                }
            )

    metadata = []
    for field in ("serial", "lineage"):
        old_value = getattr(old_state, field)
        new_value = getattr(new_state, field)
        if old_value != new_value:
            metadata.append({"field": field, "old": old_value, "new": new_value})

    return {
        "metadata": metadata,
        "removed": removed,
        "added": added,
        "modified": modified,
        "summary": {
            "resources_added": len(added),
            "resources_removed": len(removed),
            "resources_modified": len(modified),
            "attributes_changed": sum(len(item["changes"]) for item in modified),
        },
    }


def _index_instances(state: State) -> dict[str, tuple[Resource, Instance]]:
    return {
        resource.full_address(index): (resource, instance)
        for resource in state.resources
        for index, instance in enumerate(resource.instances)
    }


def _compare_values(
    old: Any,
    new: Any,
    path: tuple[str | int, ...] = (),
) -> list[dict[str, Any]]:
    if old is _MISSING:
        return _expand_change("added", new, path)
    if new is _MISSING:
        return _expand_change("removed", old, path)

    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(old.keys() | new.keys()):
            changes.extend(
                _compare_values(
                    old.get(key, _MISSING),
                    new.get(key, _MISSING),
                    (*path, key),
                )
            )
        return changes

    if isinstance(old, list) and isinstance(new, list):
        changes = []
        for index in range(max(len(old), len(new))):
            changes.extend(
                _compare_values(
                    old[index] if index < len(old) else _MISSING,
                    new[index] if index < len(new) else _MISSING,
                    (*path, index),
                )
            )
        return changes

    if old == new:
        return []
    return [
        {
            "kind": "changed",
            "path": format_attr_path(path) or "$",
            "old": old,
            "new": new,
        }
    ]


def _expand_change(
    kind: str,
    value: Any,
    path: tuple[str | int, ...],
) -> list[dict[str, Any]]:
    if isinstance(value, dict) and value:
        changes = []
        for key in sorted(value):
            changes.extend(_expand_change(kind, value[key], (*path, key)))
        return changes
    if isinstance(value, list) and value:
        changes = []
        for index, item in enumerate(value):
            changes.extend(_expand_change(kind, item, (*path, index)))
        return changes

    change = {"kind": kind, "path": format_attr_path(path) or "$"}
    change["new" if kind == "added" else "old"] = value
    return [change]
