# Terraform S3 Backend Initializer

> **Note:** This script represents the initial prototype for what will become the more comprehensive
> tfstate tool. See the main project for the structured Python implementation.

## Overview

`tf-init.sh` is a shell script that initializes a Terraform workspace backed by an S3 remote state 
and pulls the current state to a local JSON file for inspection.

This is particularly useful when:
- You need to inspect or debug a remote Terraform state without cloning the full project
- You want to analyze state data offline
- You're building tooling that works with Terraform state files
- You need to recover or migrate state between backends

## Prerequisites

- **AWS CLI** — `aws` command must be available and configured
- **Terraform** — `terraform` command must be installed
- **AWS Credentials** — Valid AWS authentication configured

## Usage

```bash
./tf-init.sh --bucket <bucket-name> --key <state-key> [--region <aws-region>]
```

### Arguments

| Argument | Required | Default | Description |
|----------|-------------|
| `--bucket` | Yes | — | S3 bucket name containing the Terraform state |
| `--key` | Yes | — | Path to the state file in the bucket (e.g., `terraform.tfstate`) |
| `--region` | No | `eu-west-2` | AWS region where the bucket is located |
| `--help`, `-h` | No | — | Display usage information |

### Example

```bash
# Pull state from an S3 backend
./tf-init.sh --bucket my-terraform-state --key prod/infra/terraform.tfstate --region us-east-1
```

## How It Works

1. **Prerequisite Check**
   - Verifies `aws-cli` is installed
   - Verifies `terraform` is installed
   - Confirms AWS authentication is working

2. **Working Directory Setup**
   - Creates an isolated directory named after the state key (slashes converted to underscores)
   - Example: `--key prod/infra/terraform.tfstate` → `prod_infra_terraform.tfstate/`

3. **Backend Configuration**
   - Generates a `backend.tf` file pointing to the specified S3 bucket
   - Configures the backend with the provided bucket, key, and region

4. **Terraform Initialization**
   - Runs `terraform init` to configure the backend
   - Downloads any required providers

5. **State Pull**
   - Executes `terraform state pull` to retrieve the remote state
   - Saves the state as a timestamped JSON file: `state_{YYYYMMDD_HHMMSS}.json`
   - Handles empty state gracefully (new backends)

## Output Structure

```
<path/to/state/key>_terraform.tfstate/
├── backend.tf              # Generated backend configuration
├── .terraform/             # Terraform plugins and modules
└── state_20260111_143052.json  # Pulled state file
```

## Workflow Example

```bash
# 1. Pull state from production environment
./tf-init.sh --bucket company-tfstate --key prod/vpc/terraform.tfstate

# 2. Navigate to the created directory
cd prod_vpc_terraform.tfstate

# 3. Analyze the pulled state
cat state_20260111_143052.json | jq '.resources[] | select(.type == "aws_instance")'

# 4. Or use terraform commands
terraform state list
terraform state show 'module.vpc.aws_instance.web[0]'
```

## Troubleshooting

### AWS Authentication Failed

```
✗ AWS authentication failed
```

**Solution:** Configure AWS credentials:
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
```

### Terraform Not Found

```
✗ Terraform is not installed or not in PATH
```

**Solution:** Install Terraform using mise:
```bash
# Install mise if not already installed
curl https://mise.run | sh

# Add to shell (add to your .bashrc or .zshrc)
eval "$(mise activate bash)"

# Install Terraform
mise use -g terraform
```

### No State Found

```
ℹ No existing state found (new backend)
```

This is normal for new Terraform backends with no prior state.

## Security Considerations

⚠️ **Important:** Terraform state files may contain sensitive data:
- Secrets stored in resource attributes
- Database passwords, API keys, etc.
- Private IP addresses and resource details

**Best Practices:**
- Never commit state files to version control
- Review state content before sharing
- Clean up local state files after analysis
- Use `.gitignore` to exclude `state_*.json` files

## Limitations

- Only supports S3 backend (other backends like GCS, Azure, etc. not implemented)
- Creates a new directory each run (doesn't reuse existing workspaces)
- Requires network access to pull remote state

## Related Project

This script is the prototype for the **tfstate** tool being built in this repository.
The goal is to provide:

- State analysis and inspection
- Resource querying and filtering
- Dependency graph visualization
- State manipulation (remove, move resources)
- Cross-state diffing
- Drift detection

See the main project documentation for the Python-based implementation.

## License

MIT
