# tfstate

A Python CLI tool for debugging, analyzing, and manipulating Terraform state files.

## Overview

`tfstate` provides tools to inspect, query, and modify Terraform state files without requiring access to the original Terraform project or the Terraform binary for most operations.

## Features

- **State Inspection** — View state metadata, list resources, query by type/module/attributes
- **Dependency Analysis** — Inspect resource dependencies and dependents
- **State Diff** — Compare state files across versions
- **State Manipulation** — Remove and move resources in connected Terraform state (`rm`, `mv`)
- **Offline Analysis** — Work with pulled state JSON files directly (`pull`, `show`, `list`, `get`, `query`, `graph`, `diff`, `filter`)

## Installation

```bash
# Using uv
uv tool install tfstate

# Using pip
pip install tfstate
```

## Quick Start

```bash
# Initialize state from S3 (read-only)
tfstate init s3://my-bucket/prod/terraform.tfstate

# Initialize with real Terraform backend
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform

# View state summary
tfstate show state.json

# List all resources (non-interactive inventory)
tfstate list state.json

# Explore resources interactively (TTY; selects one and shows details)
tfstate query state.json

# Filter resources non-interactively (scriptable)
tfstate query state.json --type aws_instance
tfstate query state.json --attr tags.Environment=prod --format json
tfstate query state.json --module module.vpc --format plain

# Get detailed resource info (offline)
tfstate get state.json module.vpc.aws_vpc.main

# Dependency tree (dependents as children)
tfstate graph state.json
tfstate graph state.json --address module.vpc.aws_vpc.main --depth 2
tfstate graph state.json --format dot

# Connected mode after init (omit the file argument)
tfstate init state.json
tfstate get module.vpc.aws_vpc.main
tfstate query --type aws_instance

# Compare state snapshots
tfstate diff old.json new.json

# Write a filtered state file (offline)
tfstate filter state.json --type aws_instance --output instances.json
tfstate filter state.json --module module.vpc --exclude-type aws_subnet -o vpc.json
```

## Documentation

- [CLI reference](docs/cli.md) — All shipped commands, flags, and examples
- [Workflows](docs/WORKFLOW.md) — End-to-end guides for offline and connected modes
- [Project Specification](docs/SPEC.md) — Architecture, commands, and implementation plan

## Status

🚧 **Early Development** — See the [specification](docs/SPEC.md) for planned features and implementation phases.

## License

MIT
