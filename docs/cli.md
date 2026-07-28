# CLI reference

User guide for `tfstate` commands and shared flags.

`tfstate` works in two modes:

| Mode | State source | Notes |
|------|--------------|--------|
| **Offline** | JSON file passed as an argument | No `terraform` binary required |
| **Connected** | Session after `tfstate init` | Omit the file argument on later commands |

This page currently documents **init** and **query**. Other commands will be added here over time.

## Shared flags

`--format` / `-f` and `--debug` are available on each command. Place them **after** the subcommand:

```bash
tfstate query state.json --type aws_instance --format json
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform --debug
```

| Flag | Values | Purpose |
|------|--------|---------|
| `--format`, `-f` | `rich` (default), `json`, `plain` | Machine- or human-readable output |
| `--debug` | flag | Full stack traces (and extra init diagnostics) |

Pre-command placement (`tfstate --format json query …`) is no longer accepted.

---

## init

Initialize state from a local file or S3 for inspection (and optionally real Terraform manipulation).

### Usage

```bash
tfstate init <state-path> [OPTIONS]
```

### Arguments

- `state-path` — S3 URI (`s3://bucket/key`) or local file path

### Options

- `--profile`, `-p` — AWS profile (S3)
- `--region`, `-r` — AWS region (S3)
- `--terraform` — Initialize a real Terraform backend workspace (requires `terraform` in `PATH`)
- `--output`, `-o` — Custom directory: terraform workspace (with `--terraform`), or a folder that receives `state.json` in read-only mode
- `--fresh` — With `--terraform`, ignore the persisted workspace cache and use a new temp dir (does not delete the cache)
- `--format`, `-f` — Output format for the init summary (`rich`, `json`, `plain`)
- `--debug` — Full stack traces; also surfaces Terraform init / provider-cache diagnostics

### Examples

**Read-only** — parse state JSON (no Terraform binary):

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate
tfstate init ./terraform.tfstate
tfstate init ./terraform.tfstate --format json
tfstate init ./terraform.tfstate -o ./my-state-dir
```

**Terraform mode** — persist/reuse a workspace, configure the backend, run `terraform init`:

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform -o ./my-workspace
tfstate init ./terraform.tfstate --terraform --debug
tfstate init ./terraform.tfstate --terraform --fresh
```

After init, stay in the `tfstate` CLI (omit the file argument in connected mode):

```bash
tfstate show
tfstate list
tfstate query --type aws_instance
tfstate rm module.vpc.aws_instance.bastion --yes   # requires --terraform
tfstate mv aws_instance.a aws_instance.b --yes      # requires --terraform
```

### How it works

**Read-only mode** (default)

1. Loads state from S3 or a local file
2. Parses JSON and prints a summary (`--format` controls that summary)
3. Stores state in the session for later commands
4. With `-o/--output`, also writes `state.json` into that directory (directory must be empty)

**Terraform mode** (`--terraform`)

1. Loads state from S3 or a local file
2. Resolves a workspace:
   - default: `~/.cache/tfstate/workspaces/<fingerprint>/` (reused on match)
   - `-o PATH`: reuse when `.tfstate-backend.json` fingerprint matches; error on mismatch
   - `--fresh`: new temp dir; leaves the cached workspace untouched
3. Writes `backend.tf` + `.tfstate-backend.json`, then always runs `terraform init`
4. Enables connected manipulation via `tfstate rm` / `tfstate mv`

Provider binaries are shared via `TF_PLUGIN_CACHE_DIR`. Workspace reuse and troubleshooting: [Provider cache](provider-cache.md).

---

## query

Explore resources interactively, or filter them non-interactively.

### Usage

```bash
# Offline
tfstate query <state-file> [OPTIONS]

# Connected (after init)
tfstate query [OPTIONS]
```

### Modes

| How you invoke it | Behavior |
|-------------------|----------|
| Bare `query` on a TTY with rich format | Interactive picker → shows `get`-style details for the selection |
| Any filter (`--type`, `--module`, `--attr`, …) | Non-interactive list of matching addresses |
| `--interactive` / `-i` | Force the picker (TTY required) |
| `--format json` or `plain` | Always non-interactive (no picker) |

`--interactive` cannot be combined with `--format json` or `--format plain`.

Bare `query` outside a usable TTY exits with an error: use `tfstate list`, add filters, or pass `--interactive` on a real terminal.

### Filters

All filters combine with **AND**. Repeat a flag for multiple conditions.

| Flag | Meaning | Example |
|------|---------|---------|
| `--type`, `-t` | Resource type | `--type aws_instance` |
| `--module`, `-m` | Module path prefix | `--module module.vpc` |
| `--attr` | Attribute equals value (`KEY=VALUE`) | `--attr tags.Environment=prod` |
| `--has-attr` | Attribute path exists | `--has-attr tags.Name` |
| `--missing-attr` | Attribute path is absent | `--missing-attr tags.Owner` |

#### Attribute paths

Paths use dots for nested objects and `[n]` for list indexes:

- `tags.Environment`
- `ports[1]`

#### `--attr` values

The right-hand side is parsed as JSON when possible (`true`, `3`, lists); otherwise it is treated as a string:

```bash
tfstate query state.json --attr tags.Environment=prod
tfstate query state.json --attr enabled=true --attr count=3
```

#### Presence vs absence

- `--has-attr path` — the path exists on the resource (including when the value is JSON `null`)
- `--missing-attr path` — the path is not present on the resource

### Examples

```bash
# Interactive explore (TTY)
tfstate query state.json

# Filter by type / module
tfstate query state.json --type aws_instance
tfstate query state.json --module module.vpc

# Attribute filters
tfstate query state.json --attr tags.Environment=prod --format json
tfstate query state.json --has-attr tags.Name
tfstate query state.json --missing-attr tags.Owner

# Combine filters (AND)
tfstate query state.json --type aws_instance --attr tags.Environment=prod --has-attr tags.Name

# Connected mode after init
tfstate init state.json
tfstate query --type aws_instance
```
