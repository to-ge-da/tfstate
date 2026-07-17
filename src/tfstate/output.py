import json
from enum import Enum
from rich.console import Console
from typing import Optional
from tfstate.attrs import format_attr_path, format_attr_value, walk_attributes
from tfstate.models import State


console = Console()

_current_format: str = "rich"


class OutputFormat(str, Enum):
    RICH = "rich"
    JSON = "json"
    PLAIN = "plain"


def configure(fmt: str) -> None:
    global _current_format
    _current_format = fmt


def get_format() -> str:
    return _current_format


def resolve_yes(yes: bool, force: bool) -> bool:
    """Resolve --force (deprecated) into --yes, emitting a warning."""
    if force:
        if not yes:
            console.print("[yellow]Warning: --force is deprecated, use --yes instead[/yellow]")
        return True
    return yes


def print_init(
    state: State,
    source: str,
    backend: str,
    terraform_mode: bool = False,
    workspace: Optional[str] = None,
) -> None:
    by_type = state.resources_by_type()
    total_resources = sum(len(resources) for resources in by_type.values())
    total_instances = sum(len(r.instances) for resources in by_type.values() for r in resources)

    fmt = get_format()
    if fmt == "json":
        data = {
            "source": source,
            "terraform_version": state.terraform_version,
            "serial": state.serial,
            "lineage": state.lineage,
            "terraform_mode": terraform_mode,
            "workspace": workspace,
            "resources": {
                "total": total_resources,
                "instances": total_instances,
                "by_type": {
                    t: sum(len(r.instances) for r in resources)
                    for t, resources in sorted(by_type.items())
                },
            },
            "outputs": list(sorted(state.outputs.keys())),
        }
        print(json.dumps(data, indent=2, default=str))
        return
    if fmt == "plain":
        mode_label = "Terraform backend" if terraform_mode else f"{backend} backend"
        print(f"\nInitialized state from {mode_label}")
        print(f"Source: {source}")
        print(f"Terraform Version: {state.terraform_version}")
        print(f"Serial: {state.serial}")
        print(f"Lineage: {state.lineage}")
        if terraform_mode:
            print("Real Terraform backend initialized - state manipulation enabled")
        if workspace:
            print(f"Workspace: {workspace}")
        print(f"\nResources: {total_resources} ({total_instances} instances)")
        for res_type, resources in sorted(by_type.items()):
            instances = sum(len(r.instances) for r in resources)
            print(f"  - {res_type}: {instances}")
        if state.outputs:
            print(f"\nOutputs: {len(state.outputs)}")
            for name in sorted(state.outputs.keys()):
                print(f"  - {name}")
        return

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

    console.print(f"\n[bold]Resources:[/bold] {total_resources} ({total_instances} instances)")
    for res_type, resources in sorted(by_type.items()):
        instances = sum(len(r.instances) for r in resources)
        console.print(f"  - {res_type}: {instances}")

    if state.outputs:
        console.print(f"\n[bold]Outputs:[/bold] {len(state.outputs)}")
        for name in sorted(state.outputs.keys()):
            console.print(f"  - {name}")


def print_show(
    state: State, file_path: str = "unknown", backend_type: Optional[str] = None
) -> None:
    fmt = get_format()
    if fmt == "json":
        data = _show_data(state, file_path, backend_type)
        print(json.dumps(data, indent=2, default=str))
        return
    if fmt == "plain":
        _print_show_plain(state, file_path, backend_type)
        return

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


def _show_data(state: State, file_path: str, backend_type: Optional[str] = None) -> dict:
    by_type = state.resources_by_type()
    by_module = state.resources_by_module()
    return {
        "file": file_path,
        "backend": backend_type,
        "terraform_version": state.terraform_version,
        "serial": state.serial,
        "lineage": state.lineage,
        "resources": {
            "total": sum(len(r) for r in by_type.values()),
            "by_type": {t: len(r) for t, r in sorted(by_type.items())},
        },
        "modules": {(m or "root"): len(r) for m, r in sorted(by_module.items())}
        if len(by_module) > 1 or "" not in by_module
        else {},
        "outputs": {
            name: {"sensitive": out.sensitive} for name, out in sorted(state.outputs.items())
        },
    }


def _print_show_plain(state: State, file_path: str, backend_type: Optional[str] = None) -> None:
    print(f"State File: {file_path}")
    if backend_type:
        print(f"Backend: {backend_type}")
    print(f"Terraform Version: {state.terraform_version}")
    print(f"Serial: {state.serial}")
    print(f"Lineage: {state.lineage}")

    by_type = state.resources_by_type()
    total = sum(len(resources) for resources in by_type.values())

    print(f"\nResources: {total} total")
    for res_type, resources in sorted(by_type.items()):
        print(f"  - {res_type}: {len(resources)}")

    by_module = state.resources_by_module()
    if len(by_module) > 1 or "" not in by_module:
        print("\nModules:")
        for mod, resources in sorted(by_module.items()):
            mod_name = mod if mod else "root"
            print(f"  - {mod_name} ({len(resources)} resources)")

    if state.outputs:
        print("\nOutputs:")
        for name, output in sorted(state.outputs.items()):
            sensitive_marker = " (sensitive)" if output.sensitive else ""
            print(f"  - {name}{sensitive_marker}")


def print_list(
    state: State,
    resource_type: Optional[str] = None,
    module: Optional[str] = None,
    show_all_types: bool = False,
) -> None:
    fmt = get_format()

    matched: list[str] = []
    for resource in state.resources:
        if resource_type and resource.type != resource_type:
            continue
        if module and resource.module != module:
            continue
        for i in range(len(resource.instances)):
            matched.append(resource.full_address(i))

    if fmt == "json":
        print(json.dumps(matched, indent=2))
        return
    if fmt == "plain":
        for addr in matched:
            print(addr)
        if not matched and (resource_type or module):
            _print_list_no_match_plain(state, resource_type, module, show_all_types)
        return

    for addr in matched:
        console.print(addr)

    if matched or not (resource_type or module):
        return

    _print_list_no_match_rich(state, resource_type, module, show_all_types)


def _print_list_no_match_rich(
    state: State,
    resource_type: Optional[str],
    module: Optional[str],
    show_all_types: bool,
) -> None:
    from difflib import get_close_matches

    parts = []
    if resource_type:
        parts.append(f"type: {resource_type}")
    if module:
        parts.append(f"module: {module}")
    console.print(f"[yellow]No resources found with {', '.join(parts)}[/yellow]")

    if resource_type:
        available = sorted(set(r.type for r in state.resources))
        if resource_type not in available:
            suggestions = get_close_matches(resource_type, available, n=3, cutoff=0.6)
            if suggestions:
                console.print("\n[yellow]Did you mean:[/yellow]")
                for s in suggestions:
                    console.print(f"  - {s}")
                console.print("\n[dim]Use --show-all-types to see all available types[/dim]")
                return
        display = available if show_all_types else available[:5]
        console.print(f"\nAvailable types in state ({len(available)} total):")
        for t in display:
            console.print(f"  - {t}")
        if not show_all_types and len(available) > 5:
            console.print(f"  ... and {len(available) - 5} more")

    if module:
        available_mods = sorted(set(r.module for r in state.resources if r.module))
        has_root = any(r.module is None for r in state.resources)
        mod_names = list(available_mods)
        if has_root:
            mod_names = ["(root)"] + mod_names

        if module not in available_mods and module != "":
            suggestions = get_close_matches(module, mod_names, n=3, cutoff=0.6)
            if suggestions:
                console.print("\n[yellow]Did you mean:[/yellow]")
                for s in suggestions:
                    console.print(f"  - {s}")
                return
        display = mod_names if show_all_types else mod_names[:5]
        console.print(f"\nAvailable modules in state ({len(mod_names)} total):")
        for m in display:
            console.print(f"  - {m}")
        if not show_all_types and len(mod_names) > 5:
            console.print(f"  ... and {len(mod_names) - 5} more")


def _print_list_no_match_plain(
    state: State,
    resource_type: Optional[str],
    module: Optional[str],
    show_all_types: bool,
) -> None:
    from difflib import get_close_matches

    parts = []
    if resource_type:
        parts.append(f"type: {resource_type}")
    if module:
        parts.append(f"module: {module}")
    print(f"No resources found with {', '.join(parts)}")

    if resource_type:
        available = sorted(set(r.type for r in state.resources))
        if resource_type not in available:
            suggestions = get_close_matches(resource_type, available, n=3, cutoff=0.6)
            if suggestions:
                print("\nDid you mean:")
                for s in suggestions:
                    print(f"  - {s}")
                print("\nUse --show-all-types to see all available types")
                return
        display = available if show_all_types else available[:5]
        print(f"\nAvailable types in state ({len(available)} total):")
        for t in display:
            print(f"  - {t}")
        if not show_all_types and len(available) > 5:
            print(f"  ... and {len(available) - 5} more")

    if module:
        available_mods = sorted(set(r.module for r in state.resources if r.module))
        has_root = any(r.module is None for r in state.resources)
        mod_names = list(available_mods)
        if has_root:
            mod_names = ["(root)"] + mod_names

        if module not in available_mods and module != "":
            suggestions = get_close_matches(module, mod_names, n=3, cutoff=0.6)
            if suggestions:
                print("\nDid you mean:")
                for s in suggestions:
                    print(f"  - {s}")
                return
        display = mod_names if show_all_types else mod_names[:5]
        print(f"\nAvailable modules in state ({len(mod_names)} total):")
        for m in display:
            print(f"  - {m}")
        if not show_all_types and len(mod_names) > 5:
            print(f"  ... and {len(mod_names) - 5} more")


def print_get(state: State, address: str) -> None:
    result = state.get_resource(address)
    if not result:
        raise ValueError(f"Resource not found: {address}")

    resource, idx = result
    instance = resource.instances[idx]
    dependents = find_dependents(state, address)
    full_address = resource.full_address(idx)
    attributes = [
        (format_attr_path(path), value) for path, value in walk_attributes(instance.attributes)
    ]

    fmt = get_format()
    if fmt == "json":
        data = {
            "address": full_address,
            "type": resource.type,
            "provider": resource.provider,
            "attributes": instance.attributes,
            "dependencies": instance.dependencies,
            "dependents": dependents,
        }
        print(json.dumps(data, indent=2, default=str))
        return
    if fmt == "plain":
        print(f"Resource: {full_address}")
        print(f"Type: {resource.type}")
        print(f"Provider: {resource.provider}")
        print("\nAttributes:")
        for key, value in attributes:
            print(f"  {key:<30} = {format_attr_value(value)}")
        if instance.dependencies:
            print("\nDependencies:")
            for dep in instance.dependencies:
                print(f"  - {dep}")
        if dependents:
            print("\nDependents:")
            for dep in dependents:
                print(f"  - {dep}")
        return

    console.print(f"\n[bold]Resource:[/bold] {full_address}")
    console.print(f"[bold]Type:[/bold] {resource.type}")
    console.print(f"[bold]Provider:[/bold] {resource.provider}")

    console.print("\n[bold]Attributes:[/bold]")
    for key, value in attributes:
        console.print(f"  {key:<30} = {format_attr_value(value)}")

    if instance.dependencies:
        console.print("\n[bold]Dependencies:[/bold]")
        for dep in instance.dependencies:
            console.print(f"  - {dep}")

    if dependents:
        console.print("\n[bold]Dependents:[/bold]")
        for dep in dependents:
            console.print(f"  - {dep}")


def find_dependents(state: State, address: str) -> list[str]:
    dependents = []
    for resource in state.resources:
        for index, instance in enumerate(resource.instances):
            if address in instance.dependencies:
                dependents.append(resource.full_address(index))
    return dependents


def print_query(addresses: list[str]) -> None:
    fmt = get_format()
    if fmt == "json":
        print(json.dumps(addresses, indent=2))
        return
    if not addresses:
        message = "No resources matched the query."
        if fmt == "plain":
            print(message)
        else:
            console.print(f"[yellow]{message}[/yellow]")
        return
    for address in addresses:
        if fmt == "plain":
            print(address)
        else:
            console.print(address)


def print_diff(result: dict) -> None:
    fmt = get_format()
    if fmt == "json":
        print(json.dumps(result, indent=2, default=str))
        return

    _print_metadata_notices(result["metadata"], rich=fmt == "rich")
    summary = result["summary"]
    has_differences = any(
        summary[key] for key in ("resources_added", "resources_removed", "resources_modified")
    )
    if not has_differences:
        if fmt == "plain":
            print("No differences found")
        else:
            console.print("[green]No differences found[/green]")
        return

    if result["removed"]:
        _print_diff_heading("Removed Resources:", rich=fmt == "rich")
        for resource in result["removed"]:
            _print_diff_line(
                f"  - {resource['address']} ({resource['type']})",
                style="red",
                rich=fmt == "rich",
            )

    if result["added"]:
        _print_diff_heading("Added Resources:", rich=fmt == "rich")
        for resource in result["added"]:
            _print_diff_line(
                f"  + {resource['address']} ({resource['type']})",
                style="green",
                rich=fmt == "rich",
            )

    if result["modified"]:
        _print_diff_heading("Modified Resources:", rich=fmt == "rich")
        for resource in result["modified"]:
            _print_diff_line(
                f"  ~ {resource['address']} ({resource['type']})",
                style="yellow",
                rich=fmt == "rich",
            )
            for change in resource["changes"]:
                _print_attribute_change(change, rich=fmt == "rich")

    lines = [
        f"Attributes changed: {summary['attributes_changed']}",
        f"Resources added: {summary['resources_added']}",
        f"Resources removed: {summary['resources_removed']}",
        f"Resources modified: {summary['resources_modified']}",
    ]
    if fmt == "plain":
        print()
        for line in lines:
            print(line)
    else:
        console.print()
        for line in lines:
            console.print(line)


def _print_metadata_notices(metadata: list[dict], rich: bool) -> None:
    for notice in metadata:
        line = (
            f"{notice['field'].capitalize()} differs: "
            f"{format_attr_value(notice['old'])} -> {format_attr_value(notice['new'])}"
        )
        if rich:
            console.print(line, style="cyan", markup=False)
        else:
            print(line)
    if metadata:
        console.print() if rich else print()


def _print_diff_heading(heading: str, rich: bool) -> None:
    if rich:
        console.print(f"[bold]{heading}[/bold]")
    else:
        print(heading)


def _print_diff_line(line: str, style: str, rich: bool) -> None:
    if rich:
        console.print(line, style=style, markup=False)
    else:
        print(line)


def _print_attribute_change(change: dict, rich: bool) -> None:
    kind = change["kind"]
    if kind == "added":
        line = f"      + {change['path']}: {format_attr_value(change['new'])}"
        style = "green"
    elif kind == "removed":
        line = f"      - {change['path']}: {format_attr_value(change['old'])}"
        style = "red"
    else:
        line = (
            f"      {change['path']}: {format_attr_value(change['old'])} "
            f"-> {format_attr_value(change['new'])}"
        )
        style = "yellow"
    _print_diff_line(line, style=style, rich=rich)


def print_rm(address: str, backup_path: str, new_state: State, rm_output: str) -> None:
    remaining = len(new_state.resources)
    fmt = get_format()
    if fmt == "json":
        data = {
            "address": address,
            "backup": backup_path,
            "resources_remaining": remaining,
            "output": rm_output.strip() or None,
        }
        print(json.dumps(data, indent=2, default=str))
        return
    if fmt == "plain":
        print(f"Resource removed: {address}")
        print(f"Backup: {backup_path}")
        print(f"Resources remaining: {remaining}")
        if rm_output.strip():
            print(rm_output.strip())
        return

    console.print(f"[bold green]Resource removed: {address}[/bold green]")
    console.print(f"[bold]Backup:[/bold] {backup_path}")
    console.print(f"[bold]Resources remaining:[/bold] {remaining}")
    if rm_output.strip():
        console.print(rm_output.strip())


def print_clear() -> None:
    fmt = get_format()
    if fmt == "json":
        print(json.dumps({"status": "cleared"}))
    elif fmt == "plain":
        print("Session cache cleared.")
    else:
        console.print("[green]Session cache cleared.[/green]")


def print_mv(src: str, dst: str, backup_path: str, new_state: State, mv_output: str) -> None:
    fmt = get_format()
    if fmt == "json":
        data = {
            "src": src,
            "dst": dst,
            "backup": backup_path,
            "resources": len(new_state.resources),
            "output": mv_output.strip() or None,
        }
        print(json.dumps(data, indent=2, default=str))
        return
    if fmt == "plain":
        print(f"Resource moved: {src} -> {dst}")
        print(f"Backup: {backup_path}")
        print(f"Resources: {len(new_state.resources)} total")
        if mv_output.strip():
            print(mv_output.strip())
        return

    console.print(f"[bold green]Resource moved: {src} -> {dst}[/bold green]")
    console.print(f"[bold]Backup:[/bold] {backup_path}")
    console.print(f"[bold]Resources:[/bold] {len(new_state.resources)} total")
    if mv_output.strip():
        console.print(mv_output.strip())
