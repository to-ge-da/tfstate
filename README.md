# tfstate

A Python CLI tool for debugging, analyzing, and manipulating Terraform state files.

## Overview

`tfstate` provides tools to inspect, query, and modify Terraform state files without requiring access to the original Terraform project or the Terraform binary for most operations.

## Features

- **State Inspection** — View state metadata, list resources, query by type/module/attributes
- **Dependency Analysis** — Inspect resource dependencies and dependents
- **State Diff** — Compare state files across versions
- **State Manipulation** — Remove, filter, and move resources within state files
- **Offline Analysis** — Work with pulled state JSON files directly

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

# List all resources
tfstate list state.json

# Query specific resource types
tfstate query state.json --type aws_instance

# Get detailed resource info
tfstate get state.json aws_vpc.main

# Compare state snapshots
tfstate diff old.json new.json
```

## Documentation

- [Workflows](docs/WORKFLOW.md) — End-to-end guides for offline and connected modes
- [init command](docs/init.md) — Initialize state from S3 or local files
- [Project Specification](docs/SPEC.md) — Architecture, commands, and implementation plan

## Status

🚧 **Early Development** — See the [specification](docs/SPEC.md) for planned features and implementation phases.

## License

MIT