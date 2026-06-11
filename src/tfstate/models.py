from pydantic import BaseModel, Field
from typing import Optional, Any


class Instance(BaseModel):
    schema_version: int
    attributes: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    private: Optional[str] = None


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
        if len(self.instances) > 1:
            return f"{addr}[{index}]"
        return addr


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
            if res.address == address:
                return (res, 0)
            if address.startswith(res.address):
                suffix = address[len(res.address):]
                if suffix.startswith('[') and ']' in suffix:
                    idx_str = suffix[1:suffix.index(']')]
                    try:
                        idx = int(idx_str)
                        if idx < len(res.instances):
                            return (res, idx)
                    except ValueError:
                        pass
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