# tfstate - Specification

## Project Overview

A Python CLI tool for debugging, analyzing, and manipulating Terraform state files. Born from the need to inspect and modify remote state without requiring access to the original Terraform project code.

## Goals

### Primary Goals

1. **Simplify Terraform State Debugging**
   - Provide clear, human-readable output for state inspection
   - Enable quick identification of issues in state files
   - Remove the need for complex `terraform state` command chains

2. **Enable Offline State Analysis**
   - Work with pulled state JSON files without requiring Terraform binary
   - Allow analysis of state snapshots at any point in time
   - Support state file comparison across versions

3. **Provide Safe State Manipulation**
   - Remove resources from state without full Terraform workflow
   - Filter and export subsets of state
   - Create backups before modifications

### Non-Goals

- Replacing Terraform's core state management functionality
- Real-time state synchronization with backends
- Terraform plan/apply execution
- State file corruption repair (complex edge cases)
- Using shell scripts as the primary workflow

## Architecture Decisions

### Language & Runtime

| Decision | Rationale |
|----------|-----------|
| **Python 3.12+** | Primary stack familiarity, excellent JSON handling, rich CLI ecosystem |
| **Typer** | Modern CLI framework with automatic help generation, type hints support |
| **Rich** | Beautiful terminal output, tables, syntax highlighting, progress bars |
| **Pydantic** | Data validation and models with strong typing |

### State Processing Approach

| Decision | Rationale |
|----------|-----------|
| **Direct JSON Parsing** | Terraform state is JSON internally — no need for Terraform binary for reads |
| **Read-only by default** | Analysis commands don't modify state, safe to run |
| **Explicit write flags** | Modifications require `--force` or explicit confirmation |
| **Backup before modify** | Automatic backup creation when modifying state |

### Backend Support

| Backend | Priority | Notes |
|---------|----------|-------|
| **Local file** | P1 | Primary input method — any `.tfstate` or `.json` file |
| **S3** | P1 | Direct pull from S3 backend (`tfstate pull s3://bucket/key`) |
| **GCS** | P3 | Future consideration |
| **HTTP** | P3 | Future consideration |

**Rationale:** S3 is the most common Terraform backend. Direct S3 pull is built into the Python tool for a seamless workflow.

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
| **Debug mode** | Detailed stack traces, internal state — enabled via `--debug` flag |
| **State validation** | Lenient — parse best effort, emit warnings for malformed data |
| **S3 errors** | Clear messages for auth failures, missing buckets, network issues |

### Backup Conventions

- **Naming:** `{original_file}.backup` (e.g., `state.json.backup`)
- **Behavior:** Overwrites on re-run (no retention of old backups)
- **Location:** Same directory as original file
- **Custom path:**可使用 `--backup <path>` 指定自定义位置

## Core Commands

### Phase 1: State Inspection (Debug)

#### `tfstate show <file>`

Display state metadata and summary.

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

#### `tfstate list <file>`

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

#### `tfstate get <file> <address>`

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

#### `tfstate query <file>`

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

#### `tfstate graph <file>`

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
- `--format <tree|dot|json>` — Output format (tree, Graphviz DOT, JSON)

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

#### `tfstate pull <s3Uri>`

Pull state directly from an S3 backend.

```
tfstate pull s3://my-bucket/prod/terraform.tfstate
tfstate pull s3://my-bucket/prod/terraform.tfstate --profile my-profile --region eu-west-1
```

Options:
- `--profile <name>` — AWS CLI profile to use
- `--region <region>` — AWS region (default: from profile or environment)
- `--output <path>` — Output file (default: stdout)

Behavior:
1. Authenticates using AWS SDK (supports profile, env vars, IAM role)
2. Downloads state from S3
3. Outputs to file or stdout

### Phase 2: State Manipulation

#### `tfstate rm <file> <address>`

Remove resource(s) from state.

```
tfstate rm state.json module.vpc.aws_instance.bastion
```

Options:
- `--force` — Skip confirmation prompt
- `--backup <path>` — Custom backup location (default: `state.json.backup`)

Behavior:
1. Creates backup of original state
2. Removes matching resource(s)
3. Updates serial number
4. Writes modified state

#### `tfstate filter <file> --output <path>`

Create a new state file with filtered resources.

```
tfstate filter state.json --type aws_instance --output instances.json
```

Options:
- `--type <resource_type>` — Include only this type
- `--module <module_path>` — Include only this module
- `--exclude-type <type>` — Exclude this type
- `--exclude-module <path>` — Exclude this module

#### `tfstate mv <file> <src> <dst>`

Rename/move a resource within state.

```
tfstate mv state.json aws_instance.web module.web.aws_instance.main
```

#### `tfstate import <file> <address> <id>`

Import an existing resource into state (wraps `terraform import`).

Note: This may require Terraform binary and configuration.

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
            return f"{self.module}.{self.type}.{self.name}"
        return f"{self.type}.{self.name}"

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
│   │   ├── pull.py          # pull command (S3 backend)
│   │   ├── show.py          # show command
│   │   ├── list.py          # list command
│   │   ├── get.py           # get command
│   │   ├── query.py         # query command
│   │   ├── graph.py         # graph command
│   │   ├── diff.py          # diff command
│   │   ├── rm.py            # rm command
│   │   ├── filter.py        # filter command
│   │   └── mv.py            # mv command
│   ├── output.py            # Output formatting (rich tables, etc.)
│   └── utils.py             # Helper functions
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

### Phase 1: Foundation (v0.1.0) ✅

- [x] Project setup (pyproject.toml, structure)
- [x] State parsing and models
- [x] `show` command
- [x] `list` command
- [x] `pull` command (S3 support)
- [x] Basic test coverage

### Phase 2: Inspection Commands (v0.2.0)

- [ ] `get` command
- [ ] `query` command with filters
- [ ] `graph` command (tree output)
- [ ] `diff` command
- [ ] Output format options (json, plain)

### Phase 3: Manipulation Commands (v0.3.0)

- [ ] `rm` command with backup
- [ ] `filter` command
- [ ] `mv` command
- [ ] Safety confirmations

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

## Open Questions

~~1. **Python version:** Target 3.10+ or 3.11+?~~ → **Python 3.12+**
~~2. **Package distribution:** PyPI only, or also support Homebrew/other?~~ → **PyPI only**
~~3. **Graph visualization:** Include Graphviz integration or keep external?~~ → **External only (DOT output)**
~~4. **Terraform compatibility:** Which state versions to support?~~ → **v4 only**
~~5. **Validation:** Should we validate state structure against Terraform schema?~~ → **Lenient (best effort with warnings)**

~~6. **S3 pull behavior:** Should `pull` command write to file or stdout by default?~~ → **stdout by default**

## References

- [Terraform State File Format](https://developer.hashicorp.com/terraform/language/state#state-file-format)
- [Terraform CLI State Commands](https://developer.hashicorp.com/terraform/cli/commands/state)
- Original prototype: `scripts/tf-init.sh`
