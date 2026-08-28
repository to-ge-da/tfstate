import json
from difflib import get_close_matches
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.tree import Tree

from tfstate import debug
from tfstate.models import State
from tfstate.output import console
from tfstate.parser import StateParseError, parse_state_file
from tfstate.session import load_session
from tfstate.state_store import require_state


class GraphFormat(str, Enum):
    TREE = "tree"
    DOT = "dot"
    JSON = "json"


def graph(
    state_file: Optional[Path] = None,
    address: Optional[str] = None,
    depth: Optional[int] = None,
    format: GraphFormat = GraphFormat.TREE,
) -> None:
    if depth is not None and depth < 0:
        typer.echo("Error: --depth must be >= 0", err=True)
        raise typer.Exit(1)

    try:
        state = _load_state(state_file)
    except StateParseError as e:
        debug.exit_with_traceback(e)
        return
    except RuntimeError:
        typer.echo("Error: No state loaded. Run 'tfstate init' first.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        debug.exit_with_traceback(e)
        return

    adjacency = _dependents_adjacency(state)
    addresses = list(adjacency)

    if address is not None:
        roots = _resolve_address(state, address, addresses)
    else:
        roots = _forest_roots(state, adjacency)

    trees, cycles = _expand_trees(adjacency, roots, depth)
    _warn_cycles(cycles)

    if format == GraphFormat.JSON:
        _print_json(trees, cycles)
    elif format == GraphFormat.DOT:
        _print_dot(trees)
    else:
        _print_tree(trees)


def _load_state(state_file: Optional[Path]) -> State:
    if state_file is not None:
        debug.logger.debug("Loading state from file: %s", state_file)
        return parse_state_file(state_file)

    try:
        return require_state()
    except RuntimeError:
        debug.logger.debug("No in-memory state, falling back to session cache")
        cached = load_session()
        if cached is None:
            debug.logger.debug("No session cache found either")
            raise
        state, _, _, _, _ = cached
        return state


def _instance_addresses(state: State) -> list[str]:
    return [
        resource.full_address(index)
        for resource in state.resources
        for index in range(len(resource.instances))
    ]


def _dependents_adjacency(state: State) -> dict[str, list[str]]:
    addresses = _instance_addresses(state)
    graph = {addr: [] for addr in addresses}
    for resource in state.resources:
        for index, instance in enumerate(resource.instances):
            dependent = resource.full_address(index)
            for dep in instance.dependencies:
                if dep in graph:
                    graph[dep].append(dependent)
    return graph


def _forest_roots(state: State, adjacency: dict[str, list[str]]) -> list[str]:
    in_graph = set(adjacency)
    has_parent: set[str] = set()
    for resource in state.resources:
        for index, instance in enumerate(resource.instances):
            addr = resource.full_address(index)
            if any(dep in in_graph for dep in instance.dependencies):
                has_parent.add(addr)
    roots = [addr for addr in adjacency if addr not in has_parent]
    covered: set[str] = set()

    def cover(addr: str, path: set[str]) -> None:
        if addr in covered or addr in path:
            return
        covered.add(addr)
        nested = path | {addr}
        for child in adjacency.get(addr, []):
            cover(child, nested)

    for root in roots:
        cover(root, set())
    for addr in adjacency:
        if addr not in covered:
            roots.append(addr)
            cover(addr, set())
    return roots


def _resolve_address(state: State, address: str, addresses: list[str]) -> list[str]:
    ambiguous = next(
        (
            resource
            for resource in state.resources
            if resource.address == address and len(resource.instances) > 1
        ),
        None,
    )
    if ambiguous:
        typer.echo(f"Error: Resource address is ambiguous: {address}", err=True)
        typer.echo("Use an indexed address:", err=True)
        for index in range(len(ambiguous.instances)):
            typer.echo(f"  - {ambiguous.full_address(index)}", err=True)
        raise typer.Exit(1)

    found = state.get_resource(address)
    if found is None:
        typer.echo(f"Error: Resource not found: {address}", err=True)
        suggestions = get_close_matches(address, addresses, n=3, cutoff=0.6)
        if suggestions:
            typer.echo("Did you mean:", err=True)
            for suggestion in suggestions:
                typer.echo(f"  - {suggestion}", err=True)
        raise typer.Exit(1)

    resource, index = found
    return [resource.full_address(index)]


def _expand_trees(
    adjacency: dict[str, list[str]],
    roots: list[str],
    depth: Optional[int],
) -> tuple[list[dict], list[list[str]]]:
    cycles: list[list[str]] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def walk(addr: str, path: tuple[str, ...], remaining: Optional[int]) -> dict:
        if addr in path:
            cycle = [*path[path.index(addr) :], addr]
            key = tuple(cycle)
            if key not in seen_cycles:
                seen_cycles.add(key)
                cycles.append(cycle)
            return {"address": addr, "dependents": [], "cycle": True}

        node: dict = {"address": addr, "dependents": []}
        if remaining is not None and remaining <= 0:
            return node

        next_remaining = None if remaining is None else remaining - 1
        new_path = (*path, addr)
        for child in adjacency.get(addr, []):
            node["dependents"].append(walk(child, new_path, next_remaining))
        return node

    trees = [walk(root, (), depth) for root in roots]
    return trees, cycles


def _warn_cycles(cycles: list[list[str]]) -> None:
    for cycle in cycles:
        typer.echo(f"Warning: cycle detected: {' -> '.join(cycle)}", err=True)


def _print_json(trees: list[dict], cycles: list[list[str]]) -> None:
    print(json.dumps({"trees": trees, "cycles": cycles}, indent=2))


def _print_tree(trees: list[dict]) -> None:
    if not trees:
        console.print("[dim]No resources in state[/dim]")
        return

    for node in trees:
        tree = Tree(_node_label(node))
        _add_tree_children(tree, node)
        console.print(tree)


def _add_tree_children(tree: Tree, node: dict) -> None:
    if node.get("cycle"):
        return
    for child in node["dependents"]:
        branch = tree.add(_node_label(child))
        _add_tree_children(branch, child)


def _node_label(node: dict) -> str:
    if node.get("cycle"):
        return f"{node['address']} [yellow](cycle)[/yellow]"
    return node["address"]


def _print_dot(trees: list[dict]) -> None:
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    _collect_dot(trees, nodes, edges)

    lines = ["digraph tfstate {", "  rankdir=TB;"]
    for addr in sorted(nodes):
        lines.append(f"  {_dot_quote(addr)};")
    for src, dst in sorted(edges):
        lines.append(f"  {_dot_quote(src)} -> {_dot_quote(dst)};")
    lines.append("}")
    print("\n".join(lines))


def _collect_dot(nodes: list[dict], seen: set[str], edges: set[tuple[str, str]]) -> None:
    for node in nodes:
        seen.add(node["address"])
        if node.get("cycle"):
            continue
        for child in node["dependents"]:
            edges.add((node["address"], child["address"]))
            _collect_dot([child], seen, edges)


def _dot_quote(addr: str) -> str:
    escaped = addr.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
