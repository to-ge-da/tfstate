# Terraform State Manipulation — rm and mv

This guide covers the manual manipulation of Terraform state using `terraform state rm` and `terraform state mv`. These are advanced operations with significant impacts — understand the risks before executing.

---

## Table of Contents

1. [Overview](#overview)
2. [Before You Start](#before-you-start)
3. [Resource Address Syntax](#resource-address-syntax)
4. [`terraform state rm`](#terraform-state-rm)
5. [`terraform state mv`](#terraform-state-mv)
6. [Common Scenarios](#common-scenarios)
7. [Safety Checklist](#safety-checklist)

---

## Overview

Terraform state maps your configuration to real-world infrastructure. Normally, Terraform manages this automatically through `plan` and `apply`. But some situations require manual state surgery:

- **Orphaned resources** — A resource was deleted outside Terraform (AWS console, CLI, etc.) and `apply` will fail
- **Refactoring** — You renamed a resource or moved it into a module and want to preserve the existing object
- **Recovery** — A state file is corrupted, locked too aggressively, or needs manual repair
- **Reorganization** — You are splitting or merging modules and need to reassign bindings

When you reach for these commands, you are bypassing Terraform's safety layer. Proceed with deliberate care.

---

## Before You Start

### Universal prerequisites

| Item | Why |
|------|-----|
| **Backup the state** | Take a snapshot of the current state file or use the backend's versioning |
| **Note the serial and lineage** | These are the state's versioning fields — critical if you need to restore |
| **Run `terraform plan`** | Understand what Terraform thinks before you change what it knows |
| **Use `-dry-run` first** | Both `rm` and `mv` support this — always use it |
| **Check dependents** | Removing or moving a resource that others depend on breaks the graph |
| **Coordinate with the team** | Especially for `mv` — nobody should `apply` between your state change and config push |

### Understanding state locks

By default, both commands acquire a state lock. This is good. Only disable it if you fully understand the risk:

```bash
# Avoid unless you know what you're doing
terraform state rm -lock=false <address>
```

If lock acquisition times out, use `-lock-timeout` instead of disabling locks:

```bash
terraform state rm -lock-timeout=30s <address>
```

---

## Resource Address Syntax

Both `rm` and `mv` accept [resource addresses](https://developer.hashicorp.com/terraform/cli/state/resource-addressing) that identify what you're targeting.

### Examples

| Target | Address | Notes |
|--------|---------|-------|
| Root resource | `aws_instance.bastion` | Single resource, no module |
| Resource with `count` | `aws_instance.bastion[0]` | Indexed instance |
| Resource with `for_each` | `aws_instance.bastion["prod"]` | String key, watch quoting |
| Resource in a module | `module.vpc.aws_vpc.main` | Module path prefix |
| Nested module | `module.network.module.vpc.aws_vpc.main` | Dot-separated module chain |
| Entire module | `module.vpc` | Removes/moves all resources in that module |
| Module with `count` | `module.vpc[0].aws_vpc.main` | Indexed module instances |
| Data source | `data.aws_ami.ubuntu` | Prefix with `data.` |

### Shell escaping

Brackets and quotes are special in most shells. Use single quotes on Unix:

```bash
# Correct (Unix)
terraform state rm 'aws_instance.bastion[0]'
terraform state rm 'aws_instance.bastion["prod"]'

# Wrong — shell swallows the brackets
terraform state rm aws_instance.bastion[0]
```

On Windows (PowerShell), double-quoting and escaping is required:

```powershell
# PowerShell
terraform state rm 'aws_instance.bastion[\"prod\"]'
```

---

## `terraform state rm`

```
terraform state rm [options] ADDRESS...
```

### What it does

Removes the binding between a Terraform resource address and its corresponding remote object. The remote object continues to exist in the cloud/AWS/GCP — Terraform simply forgets it.

### When to use

- A resource was deleted manually (via console, CLI, incident response) and `plan` errors when trying to refresh it
- A resource is corrupted in state and needs to be re-imported
- You are intentionally removing a resource from Terraform management without destroying it (e.g., moving to a different tool)
- You need to remove a resource that has `prevent_destroy = true` and want to bypass it

### Impact analysis

| Aspect | Impact |
|--------|--------|
| **Real object** | Survives entirely untouched — continues running/operating |
| **State** | The resource entry is removed. Serial increments |
| **Next `plan`** | Terraform will propose creating a **new** resource at the removed address |
| **Dependents** | Any resource depending on this one will have a broken reference — `plan` will fail or behave unexpectedly |
| **Name conflicts** | If the real object still exists and Terraform tries to create a new one with the same name/identifier, the operation will fail |

### Step-by-step procedure

```bash
# 1. Backup the state
#    (If using S3 backend, enable versioning on the bucket)
#    (For local state, copy the file)
cp terraform.tfstate terraform.tfstate.backup.$(date +%Y%m%d_%H%M%S)

# 2. Identify the exact resource address
terraform state list | grep <resource>

# 3. Check dependents
#    Manually review the state JSON or use:
#    (A quick way: grep the state for the address in dependency lists)
grep -A10 '"dependencies"' terraform.tfstate | grep <address>

# 4. Dry-run — see what will be removed
terraform state rm -dry-run 'module.vpc.aws_instance.bastion'

# 5. Remove the binding
terraform state rm 'module.vpc.aws_instance.bastion'

# 6. Verify removal
terraform state list | grep bastion  # should return nothing

# 7. Run plan to check for side effects
terraform plan
```

### Pitfalls

- **Removing a resource that has `count` or `for_each` but omitting the index** — targets all instances
- **Shell swallowing brackets** — use single quotes
- **Forgetting about dependents** — removing a subnet that an EKS cluster references will break the next plan
- **No confirmation prompt** — `terraform state rm` executes immediately. There is no "are you sure?"

---

## `terraform state mv`

```
terraform state mv [options] SOURCE DESTINATION
```

### What it does

Changes the address at which an existing remote object is tracked in state. The object itself is not touched — only the state binding moves from source to destination.

### When to use

- You renamed a `resource` block in configuration (e.g., `aws_instance.worker` → `aws_instance.helper`)
- You moved a `resource` block into a child module
- You restructured your module hierarchy (e.g., `module.app` → `module.parent.module.app`)
- You want to preserve the existing object during a refactor instead of creating a new one

### Impact analysis

| Aspect | Impact |
|--------|--------|
| **Real object** | Completely untouched — same physical resource |
| **State** | The entry moves from source address to destination address. Serial increments |
| **Next `plan`** | If the config has been updated to match: **no changes** (desired outcome). If the config has NOT been updated: plan will show destroying the old + creating the new |
| **Source constraint** | Source must exist in state |
| **Type constraint** | Source and destination must be the same resource type |

### The critical coordination window

This is the most dangerous aspect of `state mv`. The correct sequence is:

```
1. Update config (rename/move the resource block)
       ↓
2. Run `terraform state mv <old> <new>`
       ↓
3. No one runs `terraform apply` between steps 1 and 2
       ↓
4. Run `terraform plan` → should show "No changes"
```

If someone runs `apply` between your config change and the `state mv`, Terraform will destroy the old object and create a new one at the new address — potentially causing downtime or data loss.

**If you cannot coordinate** with your team, consider using `moved` blocks in configuration instead. These are native to Terraform and handled automatically during `plan`.

### Step-by-step procedure

```bash
# 1. Update the configuration file (rename/move the resource block)
# 2. Backup the state (as with rm)
cp terraform.tfstate terraform.tfstate.backup.$(date +%Y%m%d_%H%M%S)

# 3. Verify the source exists
terraform state list | grep 'old_name'

# 4. Dry-run — see what will be moved
terraform state mv -dry-run 'aws_instance.old_name' 'aws_instance.new_name'

# 5. Execute the move
terraform state mv 'aws_instance.old_name' 'aws_instance.new_name'

# 6. Verify
terraform state list | grep 'new_name'

# 7. Plan should show no changes
terraform plan
```

### Pitfalls

- **Mismatched resource types** — `terraform state mv packet_device.worker aws_instance.helper` will fail
- **Module moves without updating all paths** — if a resource moves from root to `module.vpc`, you must use the full path on both sides
- **count/for_each index mismatches** — moving `type.name[0]` to `type.name` (no index) requires the exact address form that matches the new config
- **Running `state mv` after someone else applied** — state may have changed under you. Refresh with `terraform state pull` first
- **Team coordination** — the most common source of disaster. Announce the window, or use `moved` blocks instead

---

## Common Scenarios

### Scenario 1: EC2 instance deleted manually

```bash
# Problem: plan fails with "ResourceNotFound" trying to refresh aws_instance.bastion

# 1. Confirm it's gone from AWS console
# 2. Check dependents
grep -r 'aws_instance.bastion' terraform.tfstate

# 3. Dry-run
terraform state rm -dry-run 'aws_instance.bastion'

# 4. Remove
terraform state rm 'aws_instance.bastion'

# 5. Plan should now succeed (Terraform will propose creating a new one)
terraform plan
```

### Scenario 2: Renaming a resource

```bash
# Problem: You renamed aws_instance.bastion to aws_instance.jumpbox in main.tf
#           Without a move, terraform plan wants to destroy bastion and create jumpbox

# 1. Backup
# 2. Dry-run
terraform state mv -dry-run 'aws_instance.bastion' 'aws_instance.jumpbox'

# 3. Coordinate — no applies during the window

# 4. Execute
terraform state mv 'aws_instance.bastion' 'aws_instance.jumpbox'

# 5. Verify
terraform plan  # should show "No changes. Your infrastructure is identical."
```

### Scenario 3: Moving a resource into a module

```bash
# Problem: You moved packet_device.worker from root into module.worker.packet_device.main

# 1. Update config (move the resource block into the module)
# 2. Dry-run
terraform state mv -dry-run 'packet_device.worker' 'module.worker.packet_device.main'

# 3. Execute
terraform state mv 'packet_device.worker' 'module.worker.packet_device.main'

# 4. Verify
terraform plan
```

### Scenario 4: Restoring from backup after a bad move

```bash
# Something went wrong after state mv — restore the backup

# 1. Find the backup
ls -la terraform.tfstate.backup.*

# 2. Push the backup state
#    (For S3 backend, upload the backup)
aws s3 cp terraform.tfstate.backup.20260111_143052 s3://bucket/prod/terraform.tfstate

#    (For local state, copy it back)
cp terraform.tfstate.backup.20260111_143052 terraform.tfstate

# 3. Verify
terraform plan

# 4. Revert the config change if needed
```

---

## Safety Checklist

| Step | `rm` | `mv` | Details |
|------|------|------|---------|
| Backup state | ✅ | ✅ | Always. Version the backup with a timestamp |
| Run `terraform plan` first | ✅ | ✅ | Understand the current state before changing it |
| Use `-dry-run` | ✅ | ✅ | Both commands accept it |
| Check dependents | ✅ | — | Especially important for `rm` — you could break the graph |
| Coordinate with team | — | ✅ | Critical for `mv` — the config-to-move window is dangerous |
| Update config before `mv` | — | ✅ | Config change should happen first, then `state mv` |
| Run `terraform plan` after | ✅ | ✅ | Verify the result is what you intended |
| Announce completion | — | ✅ | Let the team know the window is closed |

---

## Summary

| Command | Purpose | Risk level | Key flag |
|---------|---------|------------|----------|
| `terraform state rm` | Forget a resource | Medium | `-dry-run` |
| `terraform state mv` | Rename/relocate a resource | High (team coordination) | `-dry-run` |

**Golden rules:**
- Always backup first
- Always dry-run first
- Always plan after
- Never disable locks unless you fully understand the consequences
- For `mv`: coordinate with your team — the window between config change and state move is where disasters happen
