import json
from collections.abc import Iterator
from typing import Any


_MISSING = object()


def parse_attr_path(path: str) -> tuple[str | int, ...]:
    if not path:
        raise ValueError("attribute path cannot be empty")

    parts: list[str | int] = []
    position = 0
    expect_key = True

    while position < len(path):
        if expect_key:
            start = position
            while position < len(path) and path[position] not in ".[":
                if path[position] == "]":
                    raise ValueError(f"invalid attribute path: {path}")
                position += 1
            if start == position:
                raise ValueError(f"invalid attribute path: {path}")
            parts.append(path[start:position])
            expect_key = False

        while position < len(path) and path[position] == "[":
            closing = path.find("]", position + 1)
            if closing == -1:
                raise ValueError(f"invalid attribute path: {path}")
            index = path[position + 1 : closing]
            if not index.isdigit():
                raise ValueError(f"invalid attribute path: {path}")
            parts.append(int(index))
            position = closing + 1

        if position == len(path):
            break
        if path[position] != ".":
            raise ValueError(f"invalid attribute path: {path}")
        position += 1
        if position == len(path):
            raise ValueError(f"invalid attribute path: {path}")
        expect_key = True

    return tuple(parts)


def get_attr(attributes: Any, path: str) -> Any:
    current = attributes
    for part in parse_attr_path(path):
        if isinstance(part, str) and isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(part, int) and isinstance(current, list) and 0 <= part < len(current):
            current = current[part]
        else:
            return _MISSING
    return current


def is_missing(value: Any) -> bool:
    return value is _MISSING


def walk_attributes(
    value: Any, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[tuple[str | int, ...], Any]]:
    if isinstance(value, dict):
        if not value:
            yield path, value
            return
        for key in sorted(value):
            yield from walk_attributes(value[key], (*path, key))
        return
    if isinstance(value, list):
        if not value:
            yield path, value
            return
        for index, item in enumerate(value):
            yield from walk_attributes(item, (*path, index))
        return
    yield path, value


def format_attr_path(path: tuple[str | int, ...]) -> str:
    result = ""
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}" if result else part
    return result


def format_attr_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)
