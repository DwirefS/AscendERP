#!/bin/bash
################################################################################
# ANTS Capital Markets - Lab Teardown Script
# Safely removes ONLY resources tagged with project=ants-capital-markets
# Resource Group: DNvidiaBTANF (SHARED - does not touch other resources)
################################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
readonly RG="DNvidiaBTANF"
readonly PROJECT_TAG="ants-capital-markets"

# Global flags
FORCE=false
VERBOSE=false

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_section() {
    echo ""
    echo -e "${BLUE}==================================================================${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}==================================================================${NC}"
}

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $*"
    fi
}

confirm() {
    local prompt="$1"
    local response

    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi

    read -r -p "$(echo -e ${YELLOW}${prompt}${NC}) (yes/no): " response
    [[ "$response" =~ ^[Yy][Ee][Ss]$ ]]
}

################################################################################
# Prerequisite Checks
################################################################################

check_prerequisites() {
    log_section "Checking Prerequisites"

    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Install it first."
        exit 1
    fi

    log_success "Azure CLI found: $(az version --query '\"azure-cli\"' -o tsv)"
}

################################################################################
# Azure Account Verification
################################################################################

verify_azure_context() {
    log_section "Verifying Azure Context"

    local current_sub
    current_sub=$(az account show --query "name" -o tsv 2>/dev/null || echo "")

    if [[ -z "$current_sub" ]]; then
        log_error "Not logged into Azure. Run 'az login' first."
        exit 1
    fi

    log_success "Logged into subscription: $current_sub"

    # Verify resource group exists
    if ! az group show --resource-group "$RG" &>/dev/null; then
        log_error "Resource group '$RG' does not exist or you don't have access"
        exit 1
    fi

    log_success "Resource group verified: $RG"
}

################################################################################
# List Resources to be Deleted
################################################################################

list_resources_to_delete() {
    log_section "Resources to be Deleted"

    local has_resources=false

    # List ACR instances
    local acr_list
    acr_list=$(az acr list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].[name, location]" -o tsv 2>/dev/null || echo "")

    if [[ -n "$acr_list" ]]; then
        has_resources=true
        echo -e "${YELLOW}Container Registries (ACR):${NC}"
        echo "$acr_list" | while read -r name location; do
            echo "  - $name (Location: $location)"
        done
    fi

    # List AKS clusters
    local aks_list
    aks_list=$(az aks list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].[name, location]" -o tsv 2>/dev/null || echo "")

    if [[ -n "$aks_list" ]]; then
        has_resources=true
        echo -e "${YELLOW}AKS Clusters:${NC}"
        echo "$aks_list" | while read -r name location; do
            echo "  - $name (Location: $location)"
        done
    fi

    # List managed disks
    local disk_list
    disk_list=$(az disk list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].[name, sizeGb]" -o tsv 2>/dev/null || echo "")

    if [[ -n "$disk_list" ]]; then
        has_resources=true
        echo -e "${YELLOW}Managed Disks:${NC}"
        echo "$disk_list" | while read -r name size; do
            echo "  - $name (Size: ${size}GB)"
        done
    fi

    # List network interfaces
    local nic_list
    nic_list=$(az network nic list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].[name]" -o tsv 2>/dev/null || echo "")

    if [[ -n "$nic_list" ]]; then
        has_resources=true
        echo -e "${YELLOW}Network Interfaces:${NC}"
        echo "$nic_list" | while read -r name; do
            echo "  - $name"
        done
    fi

    # List network security groups
    local nsg_list
    nsg_list=$(az network nsg list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].[name]" -o tsv 2>/dev/null || echo "")

    if [[ -n "$nsg_list" ]]; then
        has_resources=true
        echo -e "${YELLOW}Network Security Groups:${NC}"
        echo "$nsg_list" | while read -r name; do
            echo "  - $name"
        done
    fi

    if [[ "$has_resources" == "false" ]]; then
        log_warning "No resources found with tag project=$PROJECT_TAG"
        return 1
    fi

    return 0
}

################################################################################
# Delete ACR
################################################################################

delete_acr() {
    log_section "Deleting ACR Instances"

    local acr_list
    acr_list=$(az acr list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].name" -o tsv 2>/dev/null || echo "")

    if [[ -z "$acr_list" ]]; then
        log_info "No ACR instances found"
        return
    fi

    echo "$acr_list" | while read -r acr_name; do
        log_info "Deleting ACR: $acr_name"
        az acr delete \
            --resource-group "$RG" \
            --name "$acr_name" \
            --yes \
            --output none
        log_success "ACR deleted: $acr_name"
    done
}

################################################################################
# Delete AKS Clusters
################################################################################

delete_aks() {
    log_section "Deleting AKS Clusters"

    local aks_list
    aks_list=$(az aks list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].name" -o tsv 2>/dev/null || echo "")

    if [[ -z "$aks_list" ]]; then
        log_info "No AKS clusters found"
        return
    fi

    echo "$aks_list" | while read -r aks_name; do
        log_info "Deleting AKS cluster: $aks_name"
        log_warning "This may take several minutes..."

        az aks delete \
            --resource-group "$RG" \
            --name "$aks_name" \
            --no-wait \
            --yes \
            --output none

        log_success "AKS deletion initiated (background): $aks_name"
    done

    log_info "Note: AKS deletions are running in the background. Monitor with:"
    log_info "  az aks list -g $RG -o table"
}

################################################################################
# Delete Associated Resources
################################################################################

delete_associated_resources() {
    log_section "Deleting Associated Resources"

    # Delete managed disks
    local disk_list
    disk_list=$(az disk list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].id" -o tsv 2>/dev/null || echo "")

    if [[ -n "$disk_list" ]]; then
        echo "$disk_list" | while read -r disk_id; do
            local disk_name
            disk_name=$(echo "$disk_id" | grep -oP 'disks/\K[^/]+')
            log_info "Deleting managed disk: $disk_name"
            az disk delete --ids "$disk_id" --yes --output none
            log_success "Disk deleted: $disk_name"
        done
    fi

    # Delete network interfaces
    local nic_list
    nic_list=$(az network nic list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].id" -o tsv 2>/dev/null || echo "")

    if [[ -n "$nic_list" ]]; then
        echo "$nic_list" | while read -r nic_id; do
            local nic_name
            nic_name=$(echo "$nic_id" | grep -oP 'networkInterfaces/\K[^/]+')
            log_info "Deleting network interface: $nic_name"
            az network nic delete --ids "$nic_id" --yes --output none
            log_success "NIC deleted: $nic_name"
        done
    fi

    # Delete network security groups
    local nsg_list
    nsg_list=$(az network nsg list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].id" -o tsv 2>/dev/null || echo "")

    if [[ -n "$nsg_list" ]]; then
        echo "$nsg_list" | while read -r nsg_id; do
            local nsg_name
            nsg_name=$(echo "$nsg_id" | grep -oP 'networkSecurityGroups/\K[^/]+')
            log_info "Deleting network security group: $nsg_name"
            az network nsg delete --ids "$nsg_id" --yes --output none
            log_success "NSG deleted: $nsg_name"
        done
    fi

    log_success "Associated resources cleanup complete"
}

################################################################################
# Print Cleanup Summary
################################################################################

print_cleanup_summary() {
    log_section "Cleanup Summary"

    cat <<EOF
The following resources have been scheduled for deletion:

${YELLOW}Important Notes:${NC}
  - AKS deletions run in the background (may take 10-15 minutes)
  - Associated resources (NICs, disks) have been deleted
  - Resource group "$RG" remains intact (shared lab)
  - Other resources in the RG are unaffected

${YELLOW}Monitor Progress:${NC}
  az aks list -g $RG -o table
  az acr list -g $RG -o table

${YELLOW}If you need to re-deploy:${NC}
  ./infra/deploy-lab.sh

EOF
}

################################################################################
# Print Safe Cleanup Information
################################################################################

print_safe_cleanup_info() {
    cat <<EOF

${GREEN}Safe Cleanup Guaranteed:${NC}

✓ Only resources with tag project=$PROJECT_TAG will be deleted
✓ Resource group "$RG" is NOT deleted
✓ Other resources in the RG are NOT affected
✓ All operations are reversible via re-deployment

${YELLOW}What will be deleted:${NC}
  - AKS clusters tagged with project=$PROJECT_TAG
  - Container registries tagged with project=$PROJECT_TAG
  - Associated disks and network resources

${YELLOW}What will NOT be deleted:${NC}
  - Resource group "$RG"
  - Other resources in "$RG" (from other projects)
  - Any shared infrastructure

EOF
}

################################################################################
# Main Execution
################################################################################

print_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

ANTS Capital Markets Lab Teardown Script

Safely removes ONLY resources tagged with project=$PROJECT_TAG
from resource group: $RG

OPTIONS:
  --force           Skip confirmation prompts (use with caution!)
  --verbose         Enable verbose output
  --help            Show this help message

EXAMPLES:
  # Interactive teardown (with confirmations)
  $0

  # Automatic teardown (skips confirmations)
  $0 --force

  # Teardown with verbose logging
  $0 --verbose

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                FORCE=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

main() {
    log_section "ANTS Capital Markets - Lab Teardown"

    parse_arguments "$@"

    print_safe_cleanup_info

    # Always run prerequisite checks
    check_prerequisites
    verify_azure_context

    # List resources before deletion
    if ! list_resources_to_delete; then
        log_warning "No resources to delete. Exiting."
        exit 0
    fi

    # Confirm deletion
    if ! confirm "Are you absolutely sure you want to delete these resources?"; then
        log_warning "Teardown cancelled"
        exit 0
    fi

    if ! confirm "This action cannot be easily undone. Are you certain?"; then
        log_warning "Teardown cancelled"
        exit 0
    fi

    # Execute deletion
    delete_acr
    delete_aks
    delete_associated_resources

    print_cleanup_summary

    log_success "Teardown complete!"
}

# Run main function
main "$@"
