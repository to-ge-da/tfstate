# Provider caching and workspace isolation

## Problem

Every `tfstate init --terraform` creates a new workspace and runs `terraform init`
from scratch. Even though provider binaries are cached globally, each init still:

- Creates a fresh `.terraform.lock.hcl` (re-resolves provider checksums from registry)
- Downloads state from S3 twice (boto3 + Terraform)
- Runs full backend initialization

Result: first init is ~2 min, and **every subsequent init** is also ~2 min — even
when the provider binary is already cached.

## Current behavior: cached binary, isolated workspace

Today `tfstate` uses a **two-layer** approach:

### Layer 1: global provider binary cache (working)

Introduced via `build_terraform_env()`:

```
~/.cache/tfstate/terraform-plugin-cache/
└── registry.terraform.io/hashicorp/aws/6.52.0/
    └── linux_amd64/terraform-provider-aws_v6.52.0_x5
```

- Set via `TF_PLUGIN_CACHE_DIR` in subprocess env
- Respects existing `TF_PLUGIN_CACHE_DIR` if already set in user environment
- Terraform symlinks from this dir into the workspace (see below)
- **Not** re-downloaded on repeat runs

### Layer 2: workspace (fresh every time — the gap)

```
/tmp/tfstate-xxxxx/           ← new temp dir every tfstate init
├── backend.tf
├── .terraform/
│   ├── providers/.../linux_amd64 -> ~/.cache/tfstate/.../linux_amd64  ← symlink
│   └── terraform.tfstate     ← pulled state
└── .terraform.lock.hcl       ← freshly generated, not shared between runs
```

Each `tfstate init --terraform`:

1. Calls `download_from_s3()` via boto3 (state fetch #1)
2. Creates a **new** temp workspace (`resolve_workspace()`)
3. Writes `backend.tf`
4. Runs `terraform init` — connects to S3 backend (state fetch #2), resolves
   provider versions/checksums from registry, populates `.terraform.lock.hcl`
5. Provider binary is symlinked from global cache (no re-download)

**The `.terraform/` directory and `.terraform.lock.hcl` are ephemeral.** They live
in a temp dir and are discarded when the process exits.

### Why resolve_workspace prevents reuse

```python
def resolve_workspace(output: Optional[str]) -> tuple[str, bool]:
    if output:
        ...
        if output_path.exists():
            if any(output_path.iterdir()):
                raise ValueError(
                    "Workspace directory exists and is not empty. ..."
                )
    return tempfile.mkdtemp(prefix="tfstate-"), False
```

- No `-o` → temp dir (always new)
- `-o existing-dir` with `.terraform/` or any file → **error: not empty**
- Only empty dirs are allowed, defeating reuse of initialized workspaces

## Layer 3: per-backend cached workspaces (implemented)

Persisted workspaces under `~/.cache/tfstate/workspaces/<fingerprint>/` so a
repeat `tfstate init --terraform` against the same backend reuses `.terraform/`
and `.terraform.lock.hcl`.

### Layout

```
~/.cache/tfstate/
├── terraform-plugin-cache/          ← global provider binary cache
│   └── registry.terraform.io/.../
└── workspaces/
    └── a3f8c2d1/                    ← fingerprint of backend identity
        ├── backend.tf
        ├── .tfstate-backend.json    ← sidecar (fingerprint + backend identity)
        ├── .terraform/
        ├── .terraform.lock.hcl
        └── terraform.tfstate        ← local backend copy (when applicable)
```

Each S3 URI (or local file) maps to a stable fingerprint. On repeat init:

- Fingerprint computed from backend identity
- Existing workspace detected via `.tfstate-backend.json` and **reused**
- `terraform init` always runs (warm path uses lock file + cached binaries)
- boto3 still downloads state for the init summary (skipping that on warm reuse
  is a follow-up)

### Init flow

```
tfstate init s3://bucket/key --terraform   (1st run)
├── boto3: download state
├── create ~/.cache/tfstate/workspaces/a3f8c2d1/
├── write backend.tf + .tfstate-backend.json
├── terraform init
│   ├── S3 backend
│   ├── resolve from registry
│   ├── write .terraform.lock.hcl
│   └── symlink from global cache
└── workspace persisted

tfstate init s3://bucket/key --terraform   (2nd run)
├── detect existing workspace a3f8c2d1 (sidecar match)
├── reuse ~/.cache/tfstate/workspaces/a3f8c2d1/
├── boto3: download state (summary; skip deferred)
├── terraform init (warm)
│   ├── S3 backend (~7s)
│   ├── Using previously-installed hashicorp/aws
│   └── lock file reused
└── ~7s total
```

### Fingerprint

| Backend | Input | Example |
|---------|-------|---------|
| S3 | `s3://{bucket}/{key}` + `profile` + `region` | `s3://my-bucket/prod/terraform.tfstate:us-east-1:my-profile` |
| Local | Resolved absolute path | `/home/user/state/terraform.tfstate` |

Hash with SHA-256, take first 8 hex chars → directory name.

### Flags

| Flag | Behavior |
|------|----------|
| *(default)* | Auto-persist under `~/.cache/tfstate/workspaces/<fp>/` |
| `-o PATH` | Use explicit path; reuse when sidecar fingerprint matches |
| `--fresh` | Ignore persisted workspace; use a new temp dir (does **not** delete the cache) |

### `-o` reuse

When `-o PATH` is given and the directory is non-empty:

- Sidecar fingerprint **matches** → reuse
- Sidecar fingerprint **mismatches** → error (conflicting backend)
- No sidecar → error (not empty / not a tfstate workspace)

### Performance

| Scenario | Before Layer 3 | With Layer 3 |
|----------|----------------|--------------|
| 1st init (cold) | ~2 min | ~2 min (same — cache + lock file built) |
| 2nd init, same backend | ~2 min | **~7s** (backend init only) |
| 2nd init, different backend | ~2 min | ~2 min (different workspace) |
| `-o` reuse | Error: not empty | Works (same backend) |

### Acceptance criteria

- [x] Second `tfstate init --terraform` against same backend reuses persisted workspace
- [x] Different backends map to different workspace directories
- [x] `--fresh` ignores persisted cache (does not delete it)
- [x] `-o` reuses when sidecar matches; errors on mismatch
- [x] Global `TF_PLUGIN_CACHE_DIR` behavior unchanged
- [x] Sidecar `.tfstate-backend.json` records fingerprint + backend identity

### Out of scope / follow-ups

- **Skip boto3 on warm reuse** — still downloads state for the summary; pull via
  `terraform state pull` after warm init instead ([#60](https://github.com/to-ge-da/tfstate/issues/60))
- **`TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE`** — not recommended
- **Cross-machine cache sync** — local by design
- **Automatic cache eviction** — manual cleanup of `~/.cache/tfstate/workspaces/`
