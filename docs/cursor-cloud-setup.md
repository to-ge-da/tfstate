# Cursor Cloud environment setup

This document describes how the development environment for `tfstate` is provisioned
in a fresh Cursor Cloud agent VM. It is intended for future agents/developers who need
to (re)build the environment from scratch.

Tooling is managed with [`mise`](https://mise.jdx.dev/): a single tool version manager
that installs `uv`, `terraform`, `gh`, `awscli`, and anything else the project needs.

## Setup steps

### 1. Install mise

```bash
curl -fsSL https://mise.run | sh
```

This installs the `mise` binary to `~/.local/bin/mise`.

### 2. mise manages the other tools

Once `mise` is installed, it installs everything else — `uv`, `terraform`, `gh`,
`awscli`, etc. (`uv` may alternatively be installed on its own, but keeping it under
`mise` means a single source of truth.) The tool set is declared in the repo's
[`mise.toml`](../mise.toml), so no versions need to be memorized.

### 3. Add mise to your shell (`~/.bashrc`)

Expose the mise-managed tools on `PATH` for login and non-interactive shells by adding
the mise shims directory to `~/.bashrc` (shims work reliably for subprocesses, e.g. when
`tfstate` shells out to `terraform`):

```bash
echo 'export PATH="$HOME/.local/share/mise/shims:$PATH"' >> ~/.bashrc
```

(`eval "$(mise activate bash)"` also works for interactive use.) Use a login shell —
`bash -lc '...'` — so these are picked up.

### 4. Install the tools with mise

From the repo root (which contains `mise.toml`):

```bash
mise trust      # trust the repo's mise.toml (one-time per machine)
mise install    # installs uv, terraform, gh, awscli, ...
```

Then install the Python dependencies with the mise-managed `uv`:

```bash
uv sync
```

### 5. Confirm the tools are installed

```bash
mise ls
```

Expected output (versions will vary because `mise.toml` tracks `latest`):

```
awscli     2.x  ~/…/mise.toml  latest
gh         2.x  ~/…/mise.toml  latest
terraform  1.x  ~/…/mise.toml  latest
uv         0.x  ~/…/mise.toml  latest
```

## Running tfstate

`tfstate` is a CLI-only tool — there is no server or web UI. See the top-level
[`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md) for the command reference.

- **Offline mode (read-only)** works with no extra tooling, operating directly on local
  state JSON, e.g.:

  ```bash
  uv run tfstate show tests/fixtures/basic.json
  uv run tfstate list tests/fixtures/basic.json
  ```

- **Connected / terraform mode** (`init --terraform`, `mv`, `rm`) shells out to the
  `terraform` binary (provided by mise). It works against a **local** state file — no AWS
  or S3 access is required, because the state is copied into a temporary workspace backed
  by a local backend:

  ```bash
  uv run tfstate init state.json --terraform
  uv run tfstate mv aws_instance.old aws_instance.new --yes
  uv run tfstate rm aws_vpc.main --yes
  ```

  Without terraform mode, write commands fail fast with
  `State manipulation requires terraform mode` — that means terraform mode wasn't enabled,
  not that the binary is missing.

## Gotchas

- **`terraform state pull` validates state**, so it rejects malformed state files. The
  repo fixture `tests/fixtures/basic.json` is a read-only test fixture and is **not**
  terraform-valid (a multi-instance resource lacks `index_key`, and an output value is
  malformed). Craft a proper state file for terraform-mode `mv`/`rm` testing.
- **`gh` is authenticated via `~/.config/gh/hosts.yml`**, so the mise-managed `gh` picks
  up the same credentials — no re-auth needed.
- **Session state** is cached under `~/.tfstate/` after `tfstate init`. Reset it with
  `uv run tfstate clear`.
