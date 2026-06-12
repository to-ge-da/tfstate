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
