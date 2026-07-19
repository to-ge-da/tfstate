# CLI reference

User guide for `tfstate` commands and shared flags.

`tfstate` works in two modes:

| Mode | State source | Notes |
|------|--------------|--------|
| **Offline** | JSON file passed as an argument | No `terraform` binary required |
| **Connected** | Session after `tfstate init` | Omit the file argument on later commands |

This page currently documents **init** and **query**. Other commands will be added here over time.

## Shared flags

These options are defined on the app callback today, so they must appear **before** the subcommand:

```bash
tfstate --format json query state.json --type aws_instance
tfstate --debug init s3://my-bucket/prod/terraform.tfstate --terraform
```

| Flag | Values | Purpose |
|------|--------|---------|
| `--format`, `-f` | `rich` (default), `json`, `plain` | Machine- or human-readable output |
| `--debug` | flag | Full stack traces (and extra init diagnostics) |

Moving these flags so they work after the subcommand is tracked in [#46](https://github.com/to-ge-da/tfstate/issues/46).

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
- `--terraform` — Initialize a real Terraform backend workspace
- `--output`, `-o` — Custom workspace directory (with `--terraform`)

Also accepts shared `--format` / `--debug` (before `init`).

### Examples

**Read-only** — download/parse state JSON (no Terraform binary):

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate
tfstate init ./terraform.tfstate
tfstate --format json init ./terraform.tfstate
```

**Terraform backend** — create a workspace, write `backend.tf`, run `terraform init`:

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform -o ./my-workspace
```

After `--terraform`, you can use Terraform in that workspace:

```bash
terraform -chdir=/tmp/tfstate-xxxxx show
terraform -chdir=/tmp/tfstate-xxxxx state list
```

### How it works

**Read-only mode**

1. Downloads state from S3 (or reads a local file)
2. Parses JSON and prints a summary
3. Stores state in the session for later commands (`show`, `list`, `query`, …)

**Terraform mode**

1. Downloads state from S3 (or uses a local path)
2. Creates a workspace (`/tmp/tfstate-*/` or `--output`)
3. Writes `backend.tf` and runs `terraform init`
4. Enables real state manipulation (`rm`, `mv`, or raw `terraform state …`)

Provider binaries are shared via `TF_PLUGIN_CACHE_DIR`. Details and troubleshooting: [Provider cache](provider-cache.md).

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

The right-hand side is parsed as JSON when possible (`true`, `3`, `"[80, 443]"`-style lists); otherwise it is treated as a string:

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
tfstate --format json query state.json --attr tags.Environment=prod
tfstate query state.json --has-attr tags.Name
tfstate query state.json --missing-attr tags.Owner

# Combine filters (AND)
tfstate query state.json --type aws_instance --attr tags.Environment=prod --has-attr tags.Name

# Connected mode after init
tfstate init state.json
tfstate query --type aws_instance
```
