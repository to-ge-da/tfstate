# Workflows

This guide documents the complete end-to-end workflows for `tfstate`, from initialization through inspection and manipulation. Each section clearly marks what is **implemented** vs **planned**.

---

## Two Modes of Operation

`tfstate` has two modes. The mode determines which commands are available.

| Mode | Requires | State source | Purpose |
|------|----------|-------------|---------|
| **Offline** | Nothing (not even terraform) | A JSON state file passed as argument | Quick inspection, debugging, diffing |
| **Connected** | `terraform` binary, `init` first | Backend (S3) or workspace | Real state inspection + manipulation |

---

## Offline Mode (JSON file)

Read-only analysis of state JSON files. No `terraform` binary needed.

```
                          ┌──────────────────┐
                          │  state.json       │
                          │  (pulled state)   │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  tfstate init     │  ← optional, just parses & displays
                          │  ./state.json     │
                          └────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
     │  show        │    │  list        │    │  query       │
     │  state.json  │    │  state.json  │    │  state.json  │
     │              │    │  --type      │    │  --type      │
     │              │    │  aws_instance│    │  --attr      │
     └──────────────┘    └──────────────┘    └──────────────┘
              │                  │                    │
              └──────────────────┼────────────────────┘
                                 ▼
                        ┌──────────────────┐
                        │  diff            │
                        │  old.json        │
                        │  new.json        │
                        └──────────────────┘
```

### Commands available in offline mode

| Command | Status | Signature |
|---------|--------|-----------|
| `show` | ✅ Implemented | `tfstate show <file>` |
| `list` | ✅ Implemented | `tfstate list <file> [--type] [--module]` |
| `pull` | ✅ Implemented | `tfstate pull s3://bucket/key` |
| `init` | ✅ Implemented | `tfstate init <file>` — parses and stores in memory |
| `get` | 📋 Planned (#9) | `tfstate get <file> <address>` |
| `query` | 📋 Planned (#6) | `tfstate query <file> [--type] [--attr]` |
| `graph` | 📋 Planned (#10) | `tfstate graph <file> [--address] [--depth]` |
| `diff` | 📋 Planned (#7) | `tfstate diff <file1> <file2>` |
| `filter` | 📋 Planned | `tfstate filter <file> --output <out>` |

### Example session (offline)

```bash
# Pull state from S3 (standalone, no init needed)
tfstate pull s3://my-bucket/prod/terraform.tfstate --output prod.json

# Inspect
tfstate show prod.json
tfstate list prod.json --type aws_instance

# Compare with another version
tfstate diff prod.json prod_previous.json
```

---

## Connected Mode (Real State)

Requires the `terraform` binary and an `init` step that connects to a real backend.

```
                          ┌──────────────────┐
                          │  S3 backend       │
                          │  s3://bucket/key  │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  tfstate init     │
                          │  s3://bucket/key  │
                          │  --terraform      │
                          │  -o ./workspace   │  ← planned (#13)
                          └────────┬─────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
              ┌──────▼──────┐           ┌────────▼────────┐
              │  tfstate     │           │  terraform       │
              │  show        │           │  -chdir=./ws     │
              │  list        │           │  state list      │
              │  get         │           │  state rm        │
              │  query       │           │  state mv        │
              └──────┬──────┘           └────────┬────────┘
                     │                           │
                     └─────────────┬─────────────┘
                                   │
                          ┌────────▼─────────┐
                          │  Safe wrapper     │  ← planned (Phase 3)
                          │  tfstate rm       │
                          │  tfstate mv       │
                          │  (auto-backup,    │
                          │   confirm prompt) │
                          └───────────────────┘
```

### Commands available in connected mode

| Command | Status | Signature |
|---------|--------|-----------|
| `init` | ✅ Implemented | `tfstate init s3://bucket/key --terraform [-o path]` |
| `show` | ✅ Offline only | 📋 Connected mode planned (#5) |
| `list` | ✅ Offline only | 📋 Connected mode planned (#5) |
| `rm` | 📋 Planned (Phase 3) | `tfstate rm <address>` |
| `mv` | 📋 Planned (Phase 3) | `tfstate mv <src> <dst>` |
| `terraform state *` | ⚠️ Manual workaround | `terraform -chdir=<workspace> state <cmd>` |

### Example session (connected)

Once Phase 2 and 3 land, the typical connected mode workflow will be:

```bash
# Connect to the real backend
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform -o ./workspace  # 📋 -o (#13)

# Inspect the live state (no file argument needed)
tfstate show                                        # 📋 connected mode (#5)
tfstate list --type aws_instance                    # 📋 connected mode (#5)
tfstate list --module module.vpc                    # 📋 connected mode (#5)

# Get detailed resource info
tfstate get module.vpc.aws_vpc.main                 # 📋 (#9)
tfstate get aws_instance.bastion                    # 📋 (#9)

# Query with filters
tfstate query --type aws_instance --attr tags.Environment=prod   # 📋 (#6)
tfstate query --has-attr tags.Name                               # 📋 (#6)
tfstate query --missing-attr tags.Owner                          # 📋 (#6)

# Resource dependency graph
tfstate graph state.json --address aws_vpc.main --depth 2       # 📋 (#10)

# Diff snapshots (offline)
tfstate diff prod_jan.json prod_feb.json                        # 📋 (#7)

# Safe state manipulation (auto-backup, confirmation prompt)
tfstate rm module.vpc.aws_instance.bastion                      # 📋 Phase 3
tfstate mv aws_instance.web module.web.aws_instance.main        # 📋 Phase 3
```

### Workaround: using terraform directly in the workspace

`init --terraform` creates a real Terraform workspace. You can use `terraform` directly there:

```bash
# Init
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform

# Find workspace path
# (Currently printed only in debug mode — planned improvement)

# Use terraform directly in the workspace
terraform -chdir=/tmp/tfstate-xxxxx state list
terraform -chdir=/tmp/tfstate-xxxxx state show aws_instance.bastion
terraform -chdir=/tmp/tfstate-xxxxx state rm aws_instance.bastion
```

---

## Hybrid: Local File + Workspace

Planned with the `-o` flag (#13). Lets you create a workspace from a local state file.

```
                          ┌──────────────────┐
                          │  state.json       │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  tfstate init     │
                          │  state.json       │
                          │  --terraform      │
                          │  -o ./workspace   │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  ./workspace/     │
                          │  └── terraform    │
                          │      .tfstate     │  ← copy of original
                          │  └── .terraform/  │  ← terraform init
                          └───────────────────┘
```

---

## Features by Phase

### Phase 1 (v0.1.0) — ✅ Implemented

| Feature | Command |
|---------|---------|
| Project structure + CLI | `tfstate <cmd>` |
| State parsing + models | internal |
| Offline show | `tfstate show <file>` |
| Offline list | `tfstate list <file> [--type] [--module]` |
| S3 pull | `tfstate pull s3://bucket/key` |
| Init (local + S3) | `tfstate init <path>` |
| Init with real backend | `tfstate init s3://... --terraform` |
| Basic tests | `pytest` |

### Phase 2 (v0.2.0) — 📋 Planned

| Issue | Feature | Command |
|-------|---------|---------|
| #5 | Connected show/list | `tfstate show` / `tfstate list` (no file arg) |
| #6 | Query command | `tfstate query [file] --type --attr` |
| #7 | Diff command | `tfstate diff <file1> <file2>` |
| #8 | Output format flags | `--format json\|plain` |
| #9 | Get command | `tfstate get [file] <address>` |
| #10 | Graph command | `tfstate graph <file> --address --depth` |
| #11 | Debug flag | `--debug` on all commands |
| #13 | Custom workspace (-o) | `init --terraform -o <path>` |

### Phase 3 (v0.3.0) — 📋 Planned

| Feature | Command |
|---------|---------|
| Safe rm (backup, confirm) | `tfstate rm [--force] <address>` |
| Safe mv | `tfstate mv <src> <dst>` |
| Filter command | `tfstate filter <file> --output <out>` |
| Confirmation workflow | Built-in safety prompts |

---

## Command Mapping

| What you want | Implemented way | Safer planned way |
|---------------|----------------|-------------------|
| See state summary | `tfstate show <file>` | `tfstate show` (after init) |
| List resources | `tfstate list <file>` | `tfstate list` (after init) |
| Remove a resource | `terraform -chdir=<ws> state rm <addr>` | `tfstate rm <addr>` |
| Move a resource | `terraform -chdir=<ws> state mv <src> <dst>` | `tfstate mv <src> <dst>` |
| Find specific resources | N/A | `tfstate query [file] --type` |
| Compare two states | N/A | `tfstate diff <file1> <file2>` |
| View dependency tree | N/A | `tfstate graph <file>` |
