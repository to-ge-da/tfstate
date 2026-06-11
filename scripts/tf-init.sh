#!/bin/bash

# Terraform S3 Backend Initializer
# Usage: ./tf-init.sh --bucket my-bucket --key path/to/state

set -euo pipefail

# Color codes for better output (if terminal supports it)
if [[ -t 1 ]]; then
    BOLD='\033[1m'
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    NC='\033[0m' # No Color
else
    BOLD=''
    GREEN=''
    BLUE=''
    YELLOW=''
    RED=''
    NC=''
fi

# Function to display usage information
usage() {
    echo -e "${BOLD}Usage:${NC} $0 --bucket <bucket-name> --key <state-key> [--region <aws-region>]"
    echo ""
    echo -e "${BOLD}Required:${NC}"
    echo "  --bucket <name>     S3 bucket name for Terraform state"
    echo "  --key <path>        Path to state file in bucket (e.g., terraform.tfstate)"
    echo ""
    echo -e "${BOLD}Optional:${NC}"
    echo "  --region <region>   AWS region (default: eu-west-2)"
    echo "  --help, -h          Show this help message"
}

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}▸${NC} ${BOLD}$1${NC}"
    echo -e "${BLUE}  $(printf '%.0s-' $(seq 1 ${#1}))${NC}"
}

# Function to print success messages
print_success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

# Function to print info messages
print_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

# Function to print error messages
print_error() {
    echo -e "  ${RED}✗${NC} $1"
}

# Function to check if aws-cli is installed
check_aws_cli() {
    print_header "Checking Prerequisites"
    
    if ! command -v aws &> /dev/null; then
        print_error "aws-cli is not installed or not in PATH"
        exit 1
    fi
    print_success "AWS CLI found: $(aws --version)"
}

# Function to check if Terraform is installed
check_terraform() {
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed or not in PATH"
        exit 1
    fi
    print_success "Terraform found: $(terraform --version | head -n1)"
}

# Function to verify AWS authentication
verify_aws_auth() {
    print_header "Verifying AWS Authentication"
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS authentication failed"
        echo ""
        echo -e "${YELLOW}Configure AWS credentials using:${NC}"
        echo "  • aws configure"
        echo "  • Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
        echo "  • IAM role (if running on EC2/ECS/Lambda)"
        exit 1
    fi
    print_success "AWS authentication verified"
}

# Function to parse command line arguments
# Sets global variables: BUCKET, STATE_KEY, REGION
parse_args() {
    # Reset global variables
    BUCKET=""
    STATE_KEY=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            --bucket)
                BUCKET="$2"
                shift 2
                ;;
            --state|--key)
                STATE_KEY="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo -e "${RED}Error:${NC} Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Set default region if not provided
    if [[ -z "${REGION:-}" ]]; then
        REGION="eu-west-2"
    fi
}

# Main function
main() {
    echo ""
    echo -e "${BOLD}Terraform S3 Backend Initializer${NC}"
    echo ""

    # Parse arguments (sets BUCKET and STATE_KEY)
    parse_args "$@"

    # Validate required arguments
    if [[ -z "$BUCKET" ]]; then
        print_error "--bucket is required"
        echo ""
        usage
        exit 1
    fi

    if [[ -z "$STATE_KEY" ]]; then
        print_error "--key is required"
        echo ""
        usage
        exit 1
    fi

    # Check prerequisites
    check_aws_cli
    check_terraform
    verify_aws_auth

    # Create isolated directory based on state key
    print_header "Setting Up Working Directory"
    
    # Replace slashes with underscores for directory name
    local DIR_NAME
    DIR_NAME=$(echo "$STATE_KEY" | tr '/' '_')
    if ! mkdir -p "$DIR_NAME"; then
        print_error "Failed to create directory $DIR_NAME"
        exit 1
    fi
    print_success "Created directory: $DIR_NAME"

    # Generate backend.tf
    print_header "Generating Backend Configuration"
    
    cat > "$DIR_NAME/backend.tf" << EOF
terraform {
  backend "s3" {
    bucket = "${BUCKET}"
    key    = "${STATE_KEY}"
    region = "${REGION}"
  }
}
EOF

    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo -e "  Bucket:   ${YELLOW}$BUCKET${NC}"
    echo -e "  Key:      ${YELLOW}$STATE_KEY${NC}"
    echo -e "  Region:   ${YELLOW}$REGION${NC}"
    echo -e "  Directory: ${YELLOW}$DIR_NAME${NC}"

    # Run terraform init
    print_header "Initializing Terraform"

    if terraform -chdir="$DIR_NAME" init -no-color; then
        echo ""
        print_success "Terraform initialized successfully!"
    else
        echo ""
        print_error "Terraform initialization failed"
        exit 1
    fi

    # Pull existing state if available
    print_header "Pulling Terraform State"

    local TIMESTAMP
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    local STATE_FILE="$DIR_NAME/state_${TIMESTAMP}.json"

    if terraform -chdir="$DIR_NAME" state pull -no-color > "$STATE_FILE" 2>&1; then
        # Check if state file has content (not empty)
        if [[ -s "$STATE_FILE" ]]; then
            print_success "State pulled successfully: state_${TIMESTAMP}.json"
        else
            # Empty state - new backend
            rm -f "$STATE_FILE"
            print_info "No existing state found (new backend)"
        fi
    else
        # State pull failed - check if it's because state doesn't exist
        if grep -q "Failed to load state\|No state found\|state snapshot is nil" "$STATE_FILE" 2>/dev/null; then
            rm -f "$STATE_FILE"
            print_info "No existing state found (new backend)"
        else
            # Real error (auth, network, etc.)
            print_error "Failed to pull state"
            cat "$STATE_FILE"
            rm -f "$STATE_FILE"
            exit 1
        fi
    fi

    echo ""
    echo -e "${GREEN}Your Terraform workspace is ready in:${NC} ${BOLD}$DIR_NAME/${NC}"
}

# Execute main function
main "$@"
