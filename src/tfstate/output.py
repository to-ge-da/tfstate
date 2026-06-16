from rich.console import Console
from typing import Optional
from tfstate.models import State


console = Console()


def print_init(
    state: State,
    source: str,
    backend: str,
    terraform_mode: bool = False,
    workspace: Optional[str] = None,
) -> None:
    mode_label = "Terraform backend" if terraform_mode else f"{backend} backend"
    console.print(f"\n[bold green]Initialized state from {mode_label}[/bold green]")
    console.print(f"[bold]Source:[/bold] {source}")
    console.print(f"[bold]Terraform Version:[/bold] {state.terraform_version}")
    console.print(f"[bold]Serial:[/bold] {state.serial}")
    console.print(f"[bold]Lineage:[/bold] {state.lineage}")

    if terraform_mode:
        console.print("[dim]Real Terraform backend initialized - state manipulation enabled[/dim]")

    if workspace:
        console.print(f"[bold]Workspace:[/bold] {workspace}")

    by_type = state.resources_by_type()
    total_resources = sum(len(resources) for resources in by_type.values())
    total_instances = sum(len(r.instances) for resources in by_type.values() for r in resources)

    console.print(f"\n[bold]Resources:[/bold] {total_resources} ({total_instances} instances)")
    for res_type, resources in sorted(by_type.items()):
        instances = sum(len(r.instances) for r in resources)
        console.print(f"  - {res_type}: {instances}")

    if state.outputs:
        console.print(f"\n[bold]Outputs:[/bold] {len(state.outputs)}")
        for name in sorted(state.outputs.keys()):
            console.print(f"  - {name}")


def print_show(state: State, file_path: str = "unknown", backend_type: Optional[str] = None) -> None:
    console.print(f"\n[bold]State File:[/bold] {file_path}")
    if backend_type:
        console.print(f"[bold]Backend:[/bold] {backend_type}")
    console.print(f"[bold]Terraform Version:[/bold] {state.terraform_version}")
    console.print(f"[bold]Serial:[/bold] {state.serial}")
    console.print(f"[bold]Lineage:[/bold] {state.lineage}")

    by_type = state.resources_by_type()
    total = sum(len(resources) for resources in by_type.values())

    console.print(f"\n[bold]Resources:[/bold] {total} total")
    for res_type, resources in sorted(by_type.items()):
        console.print(f"  - {res_type}: {len(resources)}")

    by_module = state.resources_by_module()
    if len(by_module) > 1 or "" not in by_module:
        console.print("\n[bold]Modules:[/bold]")
        for mod, resources in sorted(by_module.items()):
            mod_name = mod if mod else "root"
            console.print(f"  - {mod_name} ({len(resources)} resources)")

    if state.outputs:
        console.print("\n[bold]Outputs:[/bold]")
        for name, output in sorted(state.outputs.items()):
            sensitive_marker = " [dim](sensitive)[/dim]" if output.sensitive else ""
            console.print(f"  - {name}{sensitive_marker}")


def print_list(
    state: State, resource_type: Optional[str] = None, module: Optional[str] = None
) -> None:
    for resource in state.resources:
        if resource_type and resource.type != resource_type:
            continue
        if module and resource.module != module:
            continue

        for i in range(len(resource.instances)):
            console.print(resource.full_address(i))


def print_get(state: State, address: str) -> None:
    result = state.get_resource(address)
    if not result:
        console.print(f"[red]Resource not found: {address}[/red]")
        return

    resource, idx = result
    instance = resource.instances[idx]

    console.print(f"\n[bold]Resource:[/bold] {resource.address}")
    console.print(f"[bold]Type:[/bold] {resource.type}")
    console.print(f"[bold]Provider:[/bold] {resource.provider}")

    console.print("\n[bold]Attributes:[/bold]")
    for key, value in sorted(instance.attributes.items()):
        console.print(f"  {key:<30} = {value}")

    if instance.dependencies:
        console.print("\n[bold]Dependencies:[/bold]")
        for dep in instance.dependencies:
            console.print(f"  - {dep}")

    dependents = find_dependents(state, address)
    if dependents:
        console.print("\n[bold]Dependents:[/bold]")
        for dep in dependents:
            console.print(f"  - {dep}")


def find_dependents(state: State, address: str) -> list[str]:
    dependents = []
    for resource in state.resources:
        for instance in resource.instances:
            if address in instance.dependencies:
                dependents.append(resource.address)
    return dependents


def print_rm(address: str, backup_path: str, new_state: State, rm_output: str) -> None:
    remaining = len(new_state.resources)
    console.print(f"[bold green]Resource removed: {address}[/bold green]")
    console.print(f"[bold]Backup:[/bold] {backup_path}")
    console.print(f"[bold]Resources remaining:[/bold] {remaining}")
    if rm_output.strip():
        console.print(rm_output.strip())


def print_mv(src: str, dst: str, backup_path: str, new_state: State, mv_output: str) -> None:
    console.print(f"[bold green]Resource moved: {src} -> {dst}[/bold green]")
    console.print(f"[bold]Backup:[/bold] {backup_path}")
    console.print(f"[bold]Resources:[/bold] {len(new_state.resources)} total")
    if mv_output.strip():
        console.print(mv_output.strip())
