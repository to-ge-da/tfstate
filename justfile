# Aliases

alias sts := aws-check

# AWS & tooling

# Check current AWS identity
@aws-check:
    aws sts get-caller-identity
