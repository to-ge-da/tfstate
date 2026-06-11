import json
from pathlib import Path
from tfstate.models import State, Resource, Instance, StateOutput


class StateParseError(Exception):
    pass


def parse_state_file(path: Path) -> State:
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateParseError(f"Invalid JSON: {e}")
    except OSError as e:
        raise StateParseError(f"Cannot read file: {e}")

    return parse_state_data(data)


def parse_state_data(data: dict) -> State:
    if not isinstance(data, dict):
        raise StateParseError("State file must be a JSON object")

    version = data.get("version")
    if version is None:
        raise StateParseError("Missing required field: version")
    if version != 4:
        raise StateParseError(f"Unsupported state version: {version}. Only v4 is supported.")

    resources = []
    for i, res_data in enumerate(data.get("resources") or []):
        try:
            resources.append(parse_resource(res_data))
        except Exception as e:
            raise StateParseError(f"Error parsing resource[{i}]: {e}")

    outputs = {}
    for name, out_data in data.get("outputs", {}).items():
        outputs[name] = StateOutput(
            name=name,
            value=out_data.get("value", {}),
            sensitive=out_data.get("sensitive", False),
            type=out_data.get("type", "string"),
        )

    return State(
        version=version,
        terraform_version=data.get("terraform_version", "unknown"),
        serial=data.get("serial", 0),
        lineage=data.get("lineage", ""),
        outputs=outputs,
        resources=resources,
    )


def parse_resource(data: dict) -> Resource:
    instances = []
    for inst_data in data.get("instances") or []:
        inst = Instance(
            schema_version=inst_data.get("schema_version", 0),
            attributes=inst_data.get("attributes") or {},
            dependencies=inst_data.get("dependencies") or [],
            private=inst_data.get("private"),
        )
        instances.append(inst)

    return Resource(
        module=data.get("module"),
        mode=data.get("mode", "managed"),
        type=data.get("type", ""),
        name=data.get("name", ""),
        provider=data.get("provider", ""),
        instances=instances,
    )