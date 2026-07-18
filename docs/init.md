# tfstate init

Initialize a Terraform state for inspection or manipulation.

## Usage

```bash
tfstate init <state-path> [OPTIONS]
```

## Arguments

- `state-path` — S3 URI (`s3://bucket/key`) or local file path

## Options

- `--profile, -p TEXT` — AWS profile
- `--region, -r TEXT` — AWS region
- `--terraform` — Initialize real Terraform backend
- `--debug` — Show full stack traces

## Examples

### Read-only mode

Downloads and parses state JSON without Terraform:

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate
tfstate init ./terraform.tfstate
```

### Real Terraform backend mode

Creates a temporary workspace with `backend.tf` and runs `terraform init`:

```bash
tfstate init s3://my-bucket/prod/terraform.tfstate --terraform
```

Use Terraform directly in the workspace:

```bash
terraform -chdir=/tmp/tfstate-xxxxx show
terraform -chdir=/tmp/tfstate-xxxxx state list
terraform -chdir=/tmp/tfstate-xxxxx state rm aws_instance.bastion
```

## How it works

**Read-only mode:**
1. Downloads state from S3 (or reads local file)
2. Parses JSON and displays summary
3. State is stored for other commands

**Terraform mode:**
1. Downloads state from S3
2. Creates temporary workspace in `/tmp/tfstate-*/`
3. Writes `backend.tf` with S3 configuration
4. Runs `terraform init` in the workspace
5. You can now use `terraform` commands directly in that workspace

### Provider caching

When using `--terraform`, `tfstate` sets `TF_PLUGIN_CACHE_DIR` to
`~/.cache/tfstate/terraform-plugin-cache` so downloaded provider binaries
are shared across workspaces and not re-downloaded on every init.

If `TF_PLUGIN_CACHE_DIR` is already set in your environment, `tfstate`
respects it and does not override it.

### Debug traces

Use `--debug` to see whether the cache is applied:

```
$ tfstate init s3://my-bucket/prod/terraform.tfstate --terraform --debug
DEBUG: TF_PLUGIN_CACHE_DIR not set — defaulting to /home/user/.cache/tfstate/terraform-plugin-cache
```

If `TF_PLUGIN_CACHE_DIR` was inherited from your environment, the log will say
`inherited from environment` instead of `defaulting to`.

When `--debug` is on, `tfstate` also surfaces Terraform's own `init` output
so you can see whether providers are re-downloaded or reused:

```
- Using previously-installed hashicorp/aws v5.83.1    # cache hit
- Installing hashicorp/aws v6.52.0...                   # cache miss or first run
```

## Troubleshooting

### Provider cache is set but Terraform still downloads

If the cache directory exists and `TF_PLUGIN_CACHE_DIR` is logged
correctly in `--debug`, but Terraform still shows `Installing...`
on every run, isolate the issue outside `tfstate`:

```bash
# 1. Use the same cache path
export TF_PLUGIN_CACHE_DIR="$HOME/.cache/tfstate/terraform-plugin-cache"

# 2. Create a scratch directory and write a minimal backend.tf
mkdir -p /tmp/tf-cache-test
cat > /tmp/tf-cache-test/backend.tf << 'EOF'
terraform {
  backend "s3" {
    bucket = "your-bucket"
    key    = "path/to/state.tfstate"
    region = "us-east-1"
  }
}
EOF

# 3. Run init once
cd /tmp/tf-cache-test && terraform init

# 4. Wipe the workspace (keep the cache) and run again
rm -rf .terraform .terraform.lock.hcl
cd /tmp/tf-cache-test && terraform init 2>&1 | grep -E 'Installing|previously-installed'
```

- If the second run says `Using previously-installed`, then
  Terraform's cache works, and the issue is specific to how
  `tfstate` passes the environment — check the debug traces.
- If the second run still says `Installing`, then Terraform itself
  is not respecting the cache in this setup. See the next section.
