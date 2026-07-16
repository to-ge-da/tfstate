# tfstate — Development Guide

## Project

`tfstate` is a Python CLI tool for debugging, analyzing, and manipulating Terraform state files. It wraps Terraform's state operations with a safer, more ergonomic interface.

- **Offline mode** — Inspect pulled state JSON files (no `terraform` binary required)
- **Connected mode** — Real state operations against backends via `init --terraform` (requires `terraform` binary)

## Workflow

Issue → Branch → Implement → PR → Review → Merge to main

## Conventions

### Branches & commits

Use conventional prefixes for branch names and commit messages:

| Prefix | Branch | Commit |
|--------|--------|--------|
| `feat` | `feat/init-command` | `feat: add init command` |
| `docs` | `docs/workflow-guide` | `docs: add workflow documentation` |
| `fix` | `fix/parsing-bug` | `fix: handle empty module field` |
| `refactor` | `refactor/state-store` | `refactor: simplify state access` |
| `test` | — | `test: add init edge cases` |
| `chore` | — | `chore: update dependencies` |

### Rules

- Never commit to `main`
- Never force-push
- Never commit secrets
- Always delete the feature branch after merging the PR
- Use `git` for version control, `gh` for GitHub operations (issues, PRs, merge)

### Code style

- Python 3.12+
- [Typer](https://typer.tiangolo.com/) for CLI, [Rich](https://rich.readthedocs.io/) for terminal output, [Pydantic](https://docs.pydantic.dev/) for data models
- No explanatory comments unless explicitly asked
- Follow patterns in the file you're modifying
- Use `ruff` for linting and formatting
- Tests use `pytest` with `CliRunner` from `typer.testing`
- Commands live in `src/tfstate/commands/`, one file per command

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run tfstate <command>

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/
```

## Cursor Cloud specific instructions

`tfstate` is a CLI-only tool (no server/web UI); "running the app" means `uv run tfstate <command>`. Tooling (`uv`, `terraform`, `gh`, `awscli`) is managed by [`mise`](https://mise.jdx.dev/) via the repo's [`mise.toml`](mise.toml), and dependencies are refreshed on startup by `mise install` + `uv sync`.

For full environment setup, connected/terraform mode, and known gotchas, see **[`docs/cursor-cloud-setup.md`](docs/cursor-cloud-setup.md)**.
