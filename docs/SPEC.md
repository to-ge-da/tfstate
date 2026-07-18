# tfstate - Specification

## Project Overview

A Python CLI tool that wraps `terraform state` commands with a safer, more ergonomic interface. Designed for operators who need to inspect and modify real Terraform state without navigating `terraform state`'s raw CLI.

Born from the need to quickly debug and fix state issues in production without requiring access to the original Terraform project code.

## Goals

### Primary Goals

1. **Provide a Safe Wrapper for `terraform state`**
   - Clear, human-readable output for state inspection
   - Guardrails around destructive operations (explicit `init` requirement)
   - Reduce risk of accidental state corruption

2. **Enable Both Offline and Connected Workflows**
   - **Offline mode:** Quick inspection of pulled state JSON files (no terraform binary needed for read-only)
   - **Connected mode:** Real state operations via `terraform state *` (requires terraform binary)

3. **Simplify State Debugging and Manipulation**
   - Remove the need for complex `terraform state` command chains
   - Safe defaults — backup before modification, confirmation prompts
   - Rich terminal output via `rich`

### Non-Goals

- Replacing Terraform's core state management
- Terraform plan/apply execution
- Terraform Cloud / Terraform Enterprise integration
- Workspace management (out of scope for initial versions)
- Real-time state synchronization with backends

## Architecture

### Two Modes of Operation

#### Mode 1: Offline (JSON file)

Commands operate directly on a JSON state file. No terraform binary required.

Available commands: `show`, `list`, `get`, `query`, `graph`, `diff`, `pull`

```
tfstate show state.json
tfstate list state.json --type aws_instance
tfstate get state.json module.vpc.aws_vpc.main
```

#### Mode 2: Connected (Real State)

Requires `terraform` binary installed. User must run `init` first to connect to a backend.

Available commands: `show`, `list`, `get`, `query`, `rm`, `mv`

```
tfstate init s3://my-bucket/prod/terraform.tfstate
tfstate show                    # against real state
tfstate list --type aws_instance
tfstate rm module.vpc.aws_instance.bastion
```

### Safety Rules

| Rule | Enforcement |
|------|-------------|
| `init` required before `rm` or `mv` | Hard block — error if not initialized |
| Backup before modification | Automatic `.backup` file created |
| Confirmation prompt on destructive ops | Required unless `--force` |
| Read operations work without `init` | Only when a JSON file is provided |

### Dependency: Terraform Binary

`tfstate` requires the `terraform` binary for connected mode operations. Without it:
- Offline mode (JSON file inspection) still works
- Connected mode (`init`, `rm`, `mv`) is unavailable

Installation: https://developer.hashicorp.com/terraform/downloads

## Architecture Decisions

### Language & Runtime

| Decision | Rationale |
|----------|-----------|
| **Python 3.12+** | Primary stack familiarity, excellent JSON handling, rich CLI ecosystem |
| **Typer** | Modern CLI framework with automatic help generation, type hints support |
| **Rich** | Beautiful terminal output, tables, syntax highlighting |
| **Pydantic** | Data validation and models with strong typing |

### State Processing Approach

| Decision | Rationale |
|----------|-----------|
| **Direct JSON Parsing** | Terraform state is JSON — no need for binary for reads |
| **terraform state * delegation** | Connected mode delegates to terraform binary for real state operations |
| **Read-only by default** | Analysis commands don't modify state, safe to run |
| **Explicit write flags** | Modifications require `--force` or explicit confirmation |
| **Backup before modify** | Automatic backup creation when modifying state |

### Backend Support

| Backend | Priority | Notes |
|---------|----------|-------|
| **Local file** | P1 | Primary input method for offline mode |
| **S3** | P1 | Direct pull + init support |
| **GCS** | P3 | Future consideration |
| **HTTP** | P3 | Future consideration |

### Output Formats

| Format | Use Case |
|--------|----------|
| **Rich terminal** | Default — human-readable tables, colored output |
| **JSON** | Piping to other tools, automation |
| **Plain text** | Logs, simple grep-able output |

### Error Handling

| Decision | Implementation |
|----------|----------------|
| **Default mode** | User-friendly error messages, clear guidance |
| **Debug mode** | Detailed stack traces — enabled via `--debug` flag |
| **State validation** | Lenient — parse best effort, emit warnings for malformed data |
| **S3 errors** | Clear messages for auth failures, missing buckets, network issues |

### Backup Conventions

- **Naming:** `original_file}.backup` (e.g., `state.json.backup`)
- **Behavior:** Overwrites on re-run (no retention of old backups)
- **Location:** Same directory as original file
- **Custom path:** Use `--backup <path>` to specify custom location

## Core Commands

### Connected Mode: `init`

Initialize connection to a real Terraform backend.

```
tfstate init s3://my-bucket/prod/terraform.tfstate
tfstate init s3://my-bucket/prod/terraform.tfstate --profile my-profile --region eu-west-1
tfstate init ./local/terraform.tfstate
```

Options:
- `--profile <name>` — AWS CLI profile
- `--region <region>` — AWS region
- `--reconfigure` — Force re-initialization (ignore cached config)

Behavior:
1. Authenticates using AWS SDK (supports profile, env vars, IAM role)
2. Downloads current state snapshot
3. Stores backend config for subsequent commands
4. Required before any destructive command (`rm`, `mv`)

### Phase 1: State Inspection (v0.1.0) ✅

#### `tfstate show [file]`

Display state metadata and summary. If `init` has been run, shows connected state.

```
State File: state_20260111_143052.json
Terraform Version: 1.5.7
Serial: 42
Lineage: a1b2c3d4-...

Resources: 127 total
  - aws_instance: 45
  - aws_vpc: 3
  - aws_s3_bucket: 12
  - ...

Modules:
  - module.vpc (23 resources)
  - module.eks (58 resources)
```

#### `tfstate list [file]`

List all resources in state.

```
module.vpc.aws_vpc.main
module.vpc.aws_subnet.public[0]
module.vpc.aws_subnet.public[1]
module.eks.aws_eks_cluster.cluster
...
```

Options:
- `--type <resource_type>` — Filter by resource type
- `--module <module_path>` — Filter by module
- `--format <table|json|plain>` — Output format

#### `tfstate pull <s3Uri>`

Pull state directly from an S3 backend (offline mode).

```
tfstate pull s3://my-bucket/prod/terraform.tfstate
tfstate pull s3://my-bucket/prod/terraform.tfstate --profile my-profile --region eu-west-1
```

Options:
- `--profile <name>` — AWS CLI profile
- `--region <region>` — AWS region
- `--output <path>` — Output file (default: stdout)

### Phase 2: Advanced Inspection (v0.2.0)

#### `tfstate get [file] <address>`

Show detailed resource information.

```
Resource: module.vpc.aws_vpc.main
Type: aws_vpc
Provider: registry.terraform.io/hashicorp/aws

Attributes:
  cidr_block           = "10.0.0.0/16"
  id                   = "vpc-0abc123"
  tags.Name            = "production-vpc"
  instance_tenancy     = "default"
  ...

Dependencies: []
Dependents:
  - module.vpc.aws_subnet.public[0]
  - module.vpc.aws_subnet.public[1]
  - module.vpc.aws_internet_gateway.main
```

#### `tfstate query [file]`

Query resources using filters.

```
tfstate query state.json --type aws_instance --attr 'tags.Environment=prod'
```

Options:
- `--type <resource_type>` — Filter by type
- `--module <module_path>` — Filter by module path
- `--attr <expression>` — Filter by attribute (key=value)
- `--has-attr <key>` — Resources that have this attribute
- `--missing-attr <key>` — Resources missing this attribute

#### `tfstate graph [file]`

Show resource dependency graph.

```
module.vpc.aws_vpc.main
├── module.vpc.aws_subnet.public[0]
├── module.vpc.aws_subnet.public[1]
│   └── module.eks.aws_eks_cluster.cluster
│       └── module.eks.aws_eks_node_group.workers
└── module.vpc.aws_internet_gateway.main
```

Options:
- `--address <address>` — Show graph from specific resource
- `--depth <n>` — Limit graph depth
- `--format <tree|dot|json>` — Output format

#### `tfstate diff <file1> <file2>`

Compare two state files.

```
Removed Resources:
  - module.vpc.aws_instance.bastion (aws_instance)

Added Resources:
  + module.eks.aws_eks_node_group.gpu_workers (aws_eks_node_group)

Modified Resources:
  ~ module.vpc.aws_vpc.main (aws_vpc)
      cidr_block: 10.0.0.0/16 → 10.1.0.0/16
      tags.Environment: dev → prod

Attributes changed: 127
Resources added: 3
Resources removed: 1
```

### Phase 3: State Manipulation (v0.3.0) ⚠️ Requires `init`

#### `tfstate rm <address>`

Remove resource(s) from real state. Requires `init`.

```
tfstate rm module.vpc.aws_instance.bastion
```

Options:
- `--force` — Skip confirmation prompt
- `--backup <path>` — Custom backup location (default: `state.json.backup`)

Behavior:
1. Verifies `init` has been run
2. Creates backup of current state
3. Runs `terraform state rm <address>`
4. Confirms removal

#### `tfstate mv <src> <dst>`

Rename/move a resource within real state. Requires `init`.

```
tfstate mv aws_instance.web module.web.aws_instance.main
```

Behavior:
1. Verifies `init` has been run
2. Creates backup of current state
3. Runs `terraform state mv <src> <dst>`
4. Confirms move

#### `tfstate filter <file> --output <path>` (Offline)

Create a new state file with filtered resources (offline only).

```
tfstate filter state.json --type aws_instance --output instances.json
```

Options:
- `--type <resource_type>` — Include only this type
- `--module <module_path>` — Include only this module
- `--exclude-type <type>` — Exclude this type
- `--exclude-module <path>` — Exclude this module

## Data Model

### State Structure

Terraform state JSON structure (simplified):

```json
{
  "version": 4,
  "terraform_version": "1.5.7",
  "serial": 42,
  "lineage": "uuid",
  "outputs": {},
  "resources": [
    {
      "module": "module.vpc",
      "mode": "managed",
      "type": "aws_vpc",
      "name": "main",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "schema_version": 1,
          "attributes": { ... },
          "dependencies": [...],
          "private": "..."
        }
      ]
    }
  ]
}
```

### Python Models

```python
from pydantic import BaseModel
from typing import Optional

class Instance(BaseModel):
    schema_version: int
    attributes: dict
    dependencies: list[str] = []
    private: Optional[str] = None

class Resource(BaseModel):
    module: Optional[str] = None
    mode: str  # "managed" | "data"
    type: str
    name: str
    provider: str
    instances: list[Instance]

    @property
    def address(self) -> str:
        if self.module:
            return f"{self.module}.self.type}.self.name}"
        return f"{self.type}.self.name}"

class State(BaseModel):
    version: int
    terraform_version: str
    serial: int
    lineage: str
    outputs: dict
    resources: list[Resource]
```

## Project Structure

```
tfstate/
├── pyproject.toml           # Project config, dependencies, entry points
├── README.md                # Quick start, installation, examples
├── docs/
│   └── SPEC.md              # This document
├── src/tfstate/
│   ├── __init__.py
│   ├── cli.py               # CLI entry point (typer app)
│   ├── parser.py            # State file parsing logic
│   ├── models.py            # Pydantic models for state structure
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── init.py          # init command (connect to backend)
│   │   ├── pull.py          # pull command (S3 backend, offline)
│   │   ├── show.py          # show command
│   │   ├── list.py          # list command
│   │   ├── get.py           # get command
│   │   ├── query.py         # query command
│   │   ├── graph.py         # graph command
│   │   ├── diff.py          # diff command
│   │   ├── rm.py            # rm command (requires init)
│   │   ├── filter.py        # filter command (offline)
│   │   └── mv.py            # mv command (requires init)
│   ├── output.py            # Output formatting (rich tables, etc.)
│   └── state_manager.py     # Connected state management (init context)
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_parser.py
│   ├── test_models.py
│   ├── fixtures/            # Sample state files
│   │   ├── basic.json
│   │   ├── with_modules.json
│   │   └── large.json
│   └── test_commands/
│       ├── test_show.py
│       ├── test_list.py
│       └── ...
└── scripts/
    ├── README.md
    └── tf-init.sh          # Original prototype script
```

## Implementation Phases

### Phase 1: Foundation & Offline Inspection (v0.1.0) ✅

- [x] Project setup (pyproject.toml, structure)
- [x] State parsing and models
- [x] `show` command (offline JSON)
- [x] `list` command (offline JSON)
- [x] `pull` command (S3 support)
- [x] `init` command (S3 and local file support)
- [x] `init --terraform` (real Terraform backend)
- [x] Basic test coverage

### Phase 2: Connected Mode + Advanced Inspection (v0.2.0)

- [x] `init` command — connect to real backend, store context
- [x] Refactor `show` and `list` — work against both offline JSON and connected state
- [x] `get` command — detailed resource view
- [x] `query` command with filters (including interactive bare query)
- [ ] `graph` command (tree output)
- [x] `diff` command
- [x] Output format options (json, plain) — `--format` / `-f` on each command
- [x] `--debug` flag — on each command

### Phase 3: State Manipulation (v0.3.0)

- [x] `rm` command — with backup, confirmation, init enforcement
- [x] `mv` command — with backup, init enforcement
- [ ] `filter` command (offline only)
- [x] Safety confirmation workflow (unless `--force` / `--yes`)

### Phase 4: Polish & Extensions (v1.0.0)

- [ ] Comprehensive test coverage
- [ ] Documentation
- [ ] Graphviz DOT output for graph
- [ ] Performance optimization for large states
- [ ] GCS backend integration

## Implemented Commands

The following commands are currently available in v0.1.0:

| Command | Description | Status |
|---------|-------------|--------|
| `show` | Display state metadata and summary | ✅ |
| `list` | List all resources in state | ✅ |
| `pull` | Pull state from S3 backend | ✅ |
| `init` | Initialize state from S3 or local file | ✅ |
| `init --terraform` | Initialize real Terraform backend | ✅ |

## Open Questions

1. ~~**Python version:** Target 3.10+ or 3.11+?~~ → **Python 3.12+**
2. ~~**Package distribution:** PyPI only, or also support Homebrew/other?~~ → **PyPI only**
3. ~~**Graph visualization:** Include Graphviz integration or keep external?~~ → **External only (DOT output)**
4. ~~**Terraform compatibility:** Which state versions to support?~~ → **v4 only**
5. ~~**Validation:** Should we validate state structure against Terraform schema?~~ → **Lenient (best effort with warnings)**
6. ~~**S3 pull behavior:** Should `pull` command write to file or stdout by default?~~ → **stdout by default**
7. ~~**Init required before destructive ops?**~~ → **Yes, hard requirement for `rm` and `mv`**
8. ~~**Terraform Cloud/Enterprise support?**~~ → **No, out of scope**
9. ~~**Workspace management?**~~ → **No, out of scope for initial versions**
10. ~~**terraform binary dependency?**~~ → **Required for connected mode; offline JSON mode works without it**

## References

- [Terraform State File Format](https://developer.hashicorp.com/terraform/language/state#state-file-format)
- [Terraform CLI State Commands](https://developer.hashicorp.com/terraform/cli/commands/state)
- Original prototype: `scripts/tf-init.sh`
