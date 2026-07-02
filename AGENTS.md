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

- `tfstate` is a CLI-only tool — there is no server, web UI, or long-running process to start. "Running the app" means invoking `uv run tfstate <command>`.
- `uv` is installed at `~/.local/bin` and is on `PATH` in login shells. Dependencies are refreshed by the startup update script (`uv sync`).
- **Offline mode works out of the box.** Read-only commands operate on local JSON state files, e.g. `uv run tfstate show tests/fixtures/basic.json` and `uv run tfstate list tests/fixtures/basic.json`. Use `tests/fixtures/basic.json` as a ready-made sample state.
- **Connected/terraform mode is not available by default.** `init --terraform`, `mv`, and `rm` require the `terraform` binary (not installed) plus AWS credentials/S3 access. Without terraform mode these write commands fail fast with "State manipulation requires terraform mode"; this is expected, not a setup bug.
- Session state is cached under `~/.tfstate/` after `tfstate init`. Run `uv run tfstate clear` to reset it between local runs.
