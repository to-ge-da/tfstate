from pydantic import BaseModel, Field
from typing import Optional, Any, Sequence
import json


class Instance(BaseModel):
    schema_version: int
    attributes: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    private: Optional[str] = None
    index_key: Optional[str | int] = None


def format_instance_key(key: str | int) -> str:
    """Terraform instance suffix: [0] for count, [\"name\"] for for_each."""
    return f"[{json.dumps(key)}]"


class Resource(BaseModel):
    module: Optional[str] = None
    mode: str = "managed"
    type: str
    name: str
    provider: str
    instances: list[Instance] = Field(default_factory=list)

    @property
    def address(self) -> str:
        if self.module:
            return f"{self.module}.{self.type}.{self.name}"
        return f"{self.type}.{self.name}"

    def full_address(self, index: int = 0) -> str:
        addr = self.address
        if index < 0 or index >= len(self.instances):
            return addr
        inst = self.instances[index]
        if inst.index_key is not None:
            return f"{addr}{format_instance_key(inst.index_key)}"
        if len(self.instances) > 1:
            return f"{addr}[{index}]"
        return addr

    def matches_module(self, prefix: str) -> bool:
        """True if this resource is in `prefix` or a child module of it.

        `--module module.vpc` matches `module.vpc` and `module.vpc.network`,
        but not `module.vpc2` or the root module.
        """
        module = self.module or ""
        if module == prefix:
            return True
        return bool(prefix) and module.startswith(prefix + ".")

    def selected(
        self,
        *,
        types: Sequence[str] = (),
        modules: Sequence[str] = (),
        exclude_types: Sequence[str] = (),
        exclude_modules: Sequence[str] = (),
    ) -> bool:
        """True if this resource passes include filters and is not excluded.

        Includes of the same kind are OR (any `--type` / `--module` matches).
        Type and module includes combine with AND. Excludes win.
        """
        if types and self.type not in types:
            return False
        if modules and not any(self.matches_module(prefix) for prefix in modules):
            return False
        if exclude_types and self.type in exclude_types:
            return False
        if exclude_modules and any(self.matches_module(prefix) for prefix in exclude_modules):
            return False
        return True


class StateOutput(BaseModel):
    name: str
    value: Any = Field(default_factory=dict)
    sensitive: bool = False
    type: Any = "string"


class State(BaseModel):
    version: int
    terraform_version: str
    serial: int = 0
    lineage: str = ""
    outputs: dict[str, StateOutput] = Field(default_factory=dict)
    resources: list[Resource] = Field(default_factory=list)

    def get_resource(self, address: str) -> Optional[tuple[Resource, int]]:
        for res in self.resources:
            for i, _inst in enumerate(res.instances):
                if res.full_address(i) == address:
                    return (res, i)
            if res.address == address:
                if len(res.instances) == 1 and res.instances[0].index_key is None:
                    return (res, 0)
                return None
        return None

    def resources_by_type(self) -> dict[str, list[Resource]]:
        by_type: dict[str, list[Resource]] = {}
        for res in self.resources:
            if res.type not in by_type:
                by_type[res.type] = []
            by_type[res.type].append(res)
        return by_type

    def resources_by_module(self) -> dict[str, list[Resource]]:
        by_module: dict[str, list[Resource]] = {}
        for res in self.resources:
            mod = res.module or ""
            if mod not in by_module:
                by_module[mod] = []
            by_module[mod].append(res)
        return by_module

    def filtered(
        self,
        *,
        types: Sequence[str] = (),
        modules: Sequence[str] = (),
        exclude_types: Sequence[str] = (),
        exclude_modules: Sequence[str] = (),
    ) -> "State":
        kept = [
            resource.model_copy(deep=True)
            for resource in self.resources
            if resource.selected(
                types=types,
                modules=modules,
                exclude_types=exclude_types,
                exclude_modules=exclude_modules,
            )
        ]
        return State(
            version=self.version,
            terraform_version=self.terraform_version,
            serial=self.serial,
            lineage=self.lineage,
            outputs={name: output.model_copy(deep=True) for name, output in self.outputs.items()},
            resources=kept,
        )

    def to_v4_dict(self) -> dict:
        return {
            "version": self.version,
            "terraform_version": self.terraform_version,
            "serial": self.serial,
            "lineage": self.lineage,
            "outputs": {
                name: {
                    "value": output.value,
                    "sensitive": output.sensitive,
                    "type": output.type,
                }
                for name, output in self.outputs.items()
            },
            "resources": [_resource_to_v4(resource) for resource in self.resources],
        }


def _resource_to_v4(resource: Resource) -> dict:
    data: dict[str, Any] = {}
    if resource.module:
        data["module"] = resource.module
    data["mode"] = resource.mode
    data["type"] = resource.type
    data["name"] = resource.name
    data["provider"] = resource.provider
    data["instances"] = [_instance_to_v4(instance) for instance in resource.instances]
    return data


def _instance_to_v4(instance: Instance) -> dict:
    data: dict[str, Any] = {}
    if instance.index_key is not None:
        data["index_key"] = instance.index_key
    data["schema_version"] = instance.schema_version
    data["attributes"] = instance.attributes
    if instance.dependencies:
        data["dependencies"] = instance.dependencies
    if instance.private is not None:
        data["private"] = instance.private
    return data
