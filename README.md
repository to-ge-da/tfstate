# tf-state-debug

A Python CLI tool for debugging, analyzing, and manipulating Terraform state files.

## Overview

`tf-state-debug` provides tools to inspect, query, and modify Terraform state files without requiring access to the original Terraform project or the Terraform binary for most operations.

## Features

- **State Inspection** — View state metadata, list resources, query by type/module/attributes
- **Dependency Analysis** — Visualize resource dependency graphs
- **State Diff** — Compare state files across versions
- **State Manipulation** — Remove, filter, and move resources within state files
- **Offline Analysis** — Work with pulled state JSON files directly

## Installation

```bash
pip install tf-state-debug
```

## Quick Start

```bash
# View state summary
tf-state-debug show state.json

# List all resources
tf-state-debug list state.json

# Query specific resource types
tf-state-debug query state.json --type aws_instance

# Get detailed resource info
tf-state-debug get state.json aws_vpc.main
```

## Getting State Files

Use the included script to pull state from an S3 backend:

```bash
./scripts/tf-init.sh --bucket my-terraform-state --key prod/terraform.tfstate
```

Or use Terraform directly:

```bash
terraform state pull > state.json
```

## Documentation

- [Project Specification](docs/SPEC.md) — Architecture, commands, and implementation plan

## Status

🚧 **Early Development** — See the [specification](docs/SPEC.md) for planned features and implementation phases.

## License

MIT