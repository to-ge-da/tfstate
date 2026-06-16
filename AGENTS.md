# AGENTS

## Workflow

All work follows this structured pipeline:

1. **Issue** — Every task starts from a GitHub issue with goal, acceptance criteria, and relevant files
2. **Branch** — Create a feature branch from `main` using conventional naming (see below)
3. **Implement** — Make changes following the project conventions in this file
4. **PR** — Open a pull request against `main` with a clear description referencing the issue
5. **Review** — Review and address feedback; iterate on the branch as needed
6. **Merge** — Merge to `main`; delete the branch after merge

## Project

`tfstate` is a Python CLI tool for debugging, analyzing, and manipulating Terraform state files. It wraps Terraform's state operations with a safer, more ergonomic interface.

- **Offline mode** — Inspect pulled state JSON files (no `terraform` binary required)
- **Connected mode** — Real state operations against backends via `init --terraform` (requires `terraform` binary)

## Conventions

### Branch naming

- `feat/<description>` — new features (e.g., `feat/init-command`)
- `docs/<description>` — documentation (e.g., `docs/workflow-guide`)
- `fix/<description>` — bug fixes
- `refactor/<description>` — code refactoring

### Commit messages

Use conventional commits:

- `feat: <description>` — new feature
- `docs: <description>` — documentation changes
- `fix: <description>` — bug fix
- `refactor: <description>` — code restructuring with no functional change
- `test: <description>` — adding or updating tests
- `chore: <description>` — maintenance, tooling, dependencies

### Code style

- Python 3.12+
- [Typer](https://typer.tiangolo.com/) for CLI, [Rich](https://rich.readthedocs.io/) for terminal output, [Pydantic](https://docs.pydantic.dev/) for data models
- No explanatory comments unless explicitly asked
- Follow patterns in the file you're modifying
- Use `ruff` for linting and formatting
- Tests use `pytest` with `CliRunner` from `typer.testing`
- Commands live in `src/tfstate/commands/`, one file per command

### Issue references

- In PR bodies, reference related issues with descriptive context (not just bare numbers)
- Use closing keywords (`closes #N`) only when the PR fully resolves the issue

## Important files

| File | Purpose |
|------|---------|
| `docs/SPEC.md` | Full architecture, commands, and phased plan |
| `docs/WORKFLOW.md` | End-to-end user workflows (offline and connected) |
| `docs/terraform-state-manipulation.md` | Guide for raw `terraform state rm/mv` |
| `docs/init.md` | `init` command reference |
| `src/tfstate/cli.py` | Typer app entry point; all command wiring |
| `src/tfstate/state_store.py` | Global session context (singleton) |
| `src/tfstate/parser.py` | State JSON parsing and validation |
| `src/tfstate/models.py` | Pydantic models for state structure |
| `src/tfstate/output.py` | Rich terminal output formatting |
| `src/tfstate/commands/` | One file per CLI command |

## Current state

| Phase | Status | Key features |
|-------|--------|--------------|
| **v0.1.0** | ✅ Implemented | `show`, `list`, `pull`, `init`, `init --terraform` |
| **v0.2.0** | 📋 Planned (#5–#11, #13) | Connected mode, `query`, `diff`, `--format`, `get`, `graph`, `--debug`, `-o` workspace flag |
| **v0.3.0** | 📋 Planned | Safe `rm`/`mv`, `filter`, confirmation prompts |

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
