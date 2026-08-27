# Decision: Python Terraform/OpenTofu integration

Closes [#48](https://github.com/to-ge-da/tfstate/issues/48). Research is in that issue; this file records the choice for **this** repo.

> **Decision: Option A — keep `subprocess.run(["terraform", …])`. No new dependency.**
>
> Connected mode is a small, working wrapper around four CLI verbs. Offline JSON inspection is the product. A library would add a dep without shrinking the code that actually matters.

Reaffirms SPEC open question 10: binary required for connected mode; offline works without it. No ADR folder exists; this file is the record.

## Why this repo (not generic advice)

`python-terraform` is unmaintained — out. Remaining choice is *nothing* vs `tofupy` vs optional `py-libterraform`.

**Offline is the default path.** `show`, `list`, `get`, `query`, `diff`, `pull`, `cache`, and `init` without `--terraform` never invoke a binary. `pull` uses boto3. `parser.py` / `models.py` already parse v4 state JSON into Pydantic models. `session.py` / `output.py` only store and display `terraform_mode` / `terraform_version`.

**Connected mode is three commands, nine `subprocess.run` sites, four verbs:**

| File | Function | Command |
|------|----------|---------|
| `commands/init.py` | `init_terraform_backend` | `terraform init` |
| `commands/init.py` | `init_local_terraform_backend` | `terraform init` |
| `commands/init.py` | `pull_terraform_state` | `terraform state pull` |
| `commands/rm.py` | `rm` | pull (backup), `state rm`, pull (refresh) |
| `commands/mv.py` | `mv` | pull (backup), `state mv`, pull (refresh) |

PATH check: `check_terraform_installed()` (`shutil.which`) in `init()` for S3 and local `--terraform` paths.

Issue #48 said “one call site”; that is stale. Still: each site is `subprocess.run(..., capture_output=True, cwd=workspace)` plus a returncode check. Tests already mock `subprocess.run`.

**A lib does not remove the hard parts.** Workspace cache, sidecar fingerprints, `backend.tf` generation, `TF_PLUGIN_CACHE_DIR` (`build_terraform_env`), backups, and `--yes` prompts are ours. Wrapping `init`/`state mv` does not simplify them.

**`tofupy` (Option B) keeps the binary.** Structured Plan/Apply models are unused: SPEC non-goal is plan/apply. State models already exist. OpenTofu is unmentioned in the repo; if needed later, swap argv[0] (`terraform` → `tofu`) rather than take a wrapper.

**`py-libterraform` (Option C) is the wrong cost.** ~64 MB CGo wheel; bundled Terraform may not match the state’s `terraform_version`; `init()` must use `check=True` or failures swallow. Optional `try/except ImportError` + subprocess fallback **doubles** nine call sites. Operators using `rm`/`mv` already have a matching `terraform` on PATH. `terraform init` still downloads providers — “no binary” does not mean “no Terraform runtime”.

## Impact (if adopted — **not changing code now**)

- **Files:** none for Option A. Docs only (`docs/SPEC.md` already matches).
- **Effort:** S (this record). Option B would be M (rewrite nine sites + tests, no user win). Option C would be L (dual path, wheel, version skew).
- **Risk of staying:** low. Connected ops remain “have terraform in PATH”, which SPEC and `docs/cli.md` already document.

## Open questions from #48

| Question | Stance |
|----------|--------|
| Work without `terraform` installed? | **Offline already does.** Connected (`init --terraform`, `rm`, `mv`) keeps requiring a binary. Do not ship a 64 MB wheel to dodge PATH. |
| OpenTofu? | **Not in scope until someone needs it.** State JSON is the same. Prefer a `--bin` / `TFSTATE_BIN` later, not `tofupy`. |
| `plan` / `apply`? | **No.** SPEC non-goal. Revisit libraries only if that non-goal is reversed. |

## Next

Nothing to implement. Close #48 pointing here. Do not add `tofupy` or `py-libterraform` unless plan/apply or “no binary on the machine” becomes a real requirement.
