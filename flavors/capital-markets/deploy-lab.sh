#!/bin/bash
################################################################################
# ANTS Capital Markets - Lab Deployment Script
# Resource Group: DNvidiaBTANF (SHARED - do not modify other resources)
################################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration Variables
readonly RG="DNvidiaBTANF"
readonly LOCATION="eastus2"
readonly PROJECT_TAG="ants-capital-markets"
readonly ENVIRONMENT="lab"
readonly FLAVOR="capital-markets"

# Networking Configuration
readonly VNET_NAME="vnet-ants-lab"
readonly VNET_CIDR="10.0.0.0/16"
readonly SUBNET_AKS_NAME="subnet-aks"
readonly SUBNET_AKS_CIDR="10.0.1.0/24"
readonly SUBNET_ANF_NAME="subnet-anf"
readonly SUBNET_ANF_CIDR="10.0.2.0/24"

# Resource names (lab-sized)
readonly AKS_NAME="ants-cm-lab-aks"
readonly ACR_NAME="antscmlab"
readonly ACR_SKU="Basic"
readonly AKS_VM_SKU="Standard_B2ms"
readonly AKS_NODE_COUNT="2"

# Kubernetes deployment
readonly K8S_NAMESPACE="ants-capital-markets"
readonly K8S_MANIFESTS_DIR="infra/k8s/capital-markets"
readonly APP_NAME="capital-markets-api"
readonly DOCKER_IMAGE_NAME="ants-capital-markets"
readonly DOCKER_IMAGE_TAG="latest"

# Global flags
DRY_RUN=false
DESTROY=false
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

    read -r -p "$(echo -e ${YELLOW}${prompt}${NC}) (yes/no): " response
    [[ "$response" =~ ^[Yy][Ee][Ss]$ ]]
}

################################################################################
# Prerequisite Checks
################################################################################

check_prerequisites() {
    log_section "Checking Prerequisites"

    local missing_tools=()

    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        missing_tools+=("az (Azure CLI)")
    else
        log_success "Azure CLI found: $(az version --query '\"azure-cli\"' -o tsv)"
    fi

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    else
        log_success "kubectl found: $(kubectl version --client --short 2>/dev/null | grep -oP 'v[0-9.]+')"
    fi

    # Check helm
    if ! command -v helm &> /dev/null; then
        missing_tools+=("helm")
    else
        log_success "helm found: $(helm version --short 2>/dev/null | head -1)"
    fi

    # Check docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    else
        log_success "docker found: $(docker --version)"
    fi

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools:"
        for tool in "${missing_tools[@]}"; do
            log_error "  - $tool"
        done
        exit 1
    fi

    log_success "All prerequisites met"
}

################################################################################
# Azure Account and Subscription Verification
################################################################################

verify_azure_context() {
    log_section "Verifying Azure Context"

    # Get current subscription
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
    log_success "Location: $LOCATION"
}

################################################################################
# Cost Estimation
################################################################################

estimate_monthly_cost() {
    log_section "Monthly Cost Estimation (Lab Environment)"

    cat <<EOF
Resource Summary:
  - AKS Cluster: Standard_B2ms (2 nodes)
  - ACR Registry: Basic tier
  - Estimated monthly cost: $150-200 USD

Breakdown:
  - AKS Node Pool (2x B2ms): ~$80-100/month
  - ACR Basic: ~$40-50/month
  - Bandwidth/Storage: ~$30-50/month

NOTE: This is a shared lab environment. Ensure no duplicate deployments.
EOF
}

################################################################################
# Resource Existence Checks
################################################################################

vnet_exists() {
    az network vnet show --resource-group "$RG" --name "$VNET_NAME" &>/dev/null
}

aks_exists() {
    az aks show --resource-group "$RG" --name "$AKS_NAME" &>/dev/null
}

acr_exists() {
    az acr show --resource-group "$RG" --name "$ACR_NAME" &>/dev/null
}

################################################################################
# Create Networking (VNet and Subnets)
################################################################################

create_networking() {
    log_section "Creating Virtual Network and Subnets"

    if vnet_exists; then
        log_success "VNet '$VNET_NAME' already exists"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would create VNet '$VNET_NAME' with address space '$VNET_CIDR'"
        log_verbose "DRY RUN: Would create subnet '$SUBNET_AKS_NAME' with CIDR '$SUBNET_AKS_CIDR'"
        log_verbose "DRY RUN: Would create subnet '$SUBNET_ANF_NAME' with CIDR '$SUBNET_ANF_CIDR' (delegated to Microsoft.NetApp/volumes)"
        return
    fi

    if ! confirm "Create Virtual Network and Subnets?"; then
        log_warning "Networking creation skipped"
        return
    fi

    log_info "Creating Virtual Network '$VNET_NAME'..."
    az network vnet create \
        --resource-group "$RG" \
        --name "$VNET_NAME" \
        --address-prefix "$VNET_CIDR" \
        --tags \
            "project=${PROJECT_TAG}" \
            "environment=${ENVIRONMENT}" \
            "flavor=${FLAVOR}" \
            "managed-by=deploy-lab.sh" \
        --output none

    log_success "Virtual Network created"

    log_info "Creating AKS subnet '$SUBNET_AKS_NAME'..."
    az network vnet subnet create \
        --resource-group "$RG" \
        --vnet-name "$VNET_NAME" \
        --name "$SUBNET_AKS_NAME" \
        --address-prefix "$SUBNET_AKS_CIDR" \
        --output none

    log_success "AKS subnet created"

    log_info "Creating ANF subnet '$SUBNET_ANF_NAME' with NetApp delegation..."
    az network vnet subnet create \
        --resource-group "$RG" \
        --vnet-name "$VNET_NAME" \
        --name "$SUBNET_ANF_NAME" \
        --address-prefix "$SUBNET_ANF_CIDR" \
        --delegations "Microsoft.NetApp/volumes" \
        --output none

    log_success "ANF subnet created with NetApp delegation"
    log_success "Networking created successfully"
}

################################################################################
# Create AKS Cluster
################################################################################

create_aks_cluster() {
    log_section "Creating AKS Cluster"

    if aks_exists; then
        log_success "AKS cluster '$AKS_NAME' already exists"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would create AKS cluster '$AKS_NAME'"
        return
    fi

    if ! confirm "Create AKS cluster '$AKS_NAME'? (Cost: ~$80-100/month)"; then
        log_warning "AKS cluster creation skipped"
        return
    fi

    log_info "Creating AKS cluster (this may take 10-15 minutes)..."

    # Get AKS subnet ID
    local aks_subnet_id
    aks_subnet_id=$(az network vnet subnet show -g "$RG" --vnet-name "$VNET_NAME" -n "$SUBNET_AKS_NAME" --query id -o tsv)

    az aks create \
        --resource-group "$RG" \
        --name "$AKS_NAME" \
        --node-count "$AKS_NODE_COUNT" \
        --vm-set-type VirtualMachineScaleSets \
        --load-balancer-sku standard \
        --enable-managed-identity \
        --network-plugin azure \
        --vnet-subnet-id "$aks_subnet_id" \
        --service-cidr "172.16.0.0/16" \
        --dns-service-ip "172.16.0.10" \
        --node-vm-size "$AKS_VM_SKU" \
        --generate-ssh-keys \
        --tags \
            "project=${PROJECT_TAG}" \
            "environment=${ENVIRONMENT}" \
            "flavor=${FLAVOR}" \
            "managed-by=deploy-lab.sh" \
        --output none

    log_success "AKS cluster created successfully"
}

################################################################################
# Create Azure Container Registry
################################################################################

create_acr() {
    log_section "Creating Azure Container Registry"

    if acr_exists; then
        log_success "ACR '$ACR_NAME' already exists"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would create ACR '$ACR_NAME'"
        return
    fi

    if ! confirm "Create ACR '$ACR_NAME'? (Cost: ~$40-50/month)"; then
        log_warning "ACR creation skipped"
        return
    fi

    log_info "Creating ACR..."

    az acr create \
        --resource-group "$RG" \
        --name "$ACR_NAME" \
        --sku "$ACR_SKU" \
        --tags \
            "project=${PROJECT_TAG}" \
            "environment=${ENVIRONMENT}" \
            "flavor=${FLAVOR}" \
            "managed-by=deploy-lab.sh" \
        --output none

    log_success "ACR created successfully"
}

################################################################################
# Attach ACR to AKS
################################################################################

attach_acr_to_aks() {
    log_section "Attaching ACR to AKS"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would attach ACR to AKS"
        return
    fi

    # Get AKS service principal
    local aks_principal
    aks_principal=$(az aks show -g "$RG" -n "$AKS_NAME" --query identityProfile.kubeletidentity.objectId -o tsv)

    if [[ -z "$aks_principal" ]]; then
        log_error "Could not retrieve AKS managed identity"
        exit 1
    fi

    # Get ACR resource ID
    local acr_id
    acr_id=$(az acr show --resource-group "$RG" --name "$ACR_NAME" --query id -o tsv)

    # Check if role assignment already exists
    local existing_role
    existing_role=$(az role assignment list \
        --assignee "$aks_principal" \
        --scope "$acr_id" \
        --query "[0].id" -o tsv 2>/dev/null || echo "")

    if [[ -n "$existing_role" ]]; then
        log_success "ACR is already attached to AKS"
        return
    fi

    log_info "Attaching ACR to AKS..."
    az role assignment create \
        --assignee "$aks_principal" \
        --role acrpull \
        --scope "$acr_id" \
        --output none

    log_success "ACR attached to AKS"
}

################################################################################
# Get AKS Credentials
################################################################################

get_aks_credentials() {
    log_section "Getting AKS Credentials"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would fetch AKS credentials"
        return
    fi

    log_info "Fetching AKS credentials..."
    az aks get-credentials \
        --resource-group "$RG" \
        --name "$AKS_NAME" \
        --overwrite-existing \
        --output none

    log_success "AKS credentials configured"

    # Verify connection
    if kubectl cluster-info &>/dev/null; then
        log_success "Connected to AKS cluster"
    else
        log_error "Failed to connect to AKS cluster"
        exit 1
    fi
}

################################################################################
# Build and Push Docker Image
#
# GAP #10 — FIXED (2026-03-04)
# WHAT: Original function used local `docker build` + `docker push` which
#   requires a Docker daemon running locally. Azure Cloud Shell does NOT
#   have a Docker daemon — it's a container itself (nested Docker not available).
# WHY IT MATTERS: The deployment guide assumes you have Docker installed locally,
#   but the primary deployment path is via Cloud Shell (already authenticated).
# FIX: Added `az acr build` as primary method. This sends the build context
#   to ACR and builds the image server-side using ACR Tasks. No local Docker
#   daemon needed. Falls back to local Docker if available (for local dev).
# ORIGINAL docker build/push code preserved below (commented out) for
#   reference and for local development scenarios where Docker IS available.
################################################################################

build_and_push_image() {
    log_section "Building and Pushing Docker Image"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would build and push Docker image"
        return
    fi

    local acr_url="${ACR_NAME}.azurecr.io"
    local image_name="${acr_url}/${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"

    # Navigate to the flavor directory where Dockerfile lives
    # WHY: The Dockerfile is in flavors/capital-markets/ and expects that
    # directory as its build context (COPY . /app/ copies this folder)
    local flavor_dir
    flavor_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if Dockerfile exists in the flavor directory
    if [[ ! -f "${flavor_dir}/Dockerfile" ]]; then
        log_error "Dockerfile not found in ${flavor_dir}"
        log_info "Expected: ${flavor_dir}/Dockerfile"
        return 1
    fi

    # -------------------------------------------------------------------------
    # Primary method: az acr build (Cloud Shell / no Docker daemon required)
    # WHY: ACR Tasks builds the image server-side using Azure-managed compute.
    #   The build context (Dockerfile + source code) is uploaded to ACR,
    #   built there, and the resulting image is pushed to the registry —
    #   all in one command. No local Docker needed.
    # -------------------------------------------------------------------------
    if command -v az &> /dev/null; then
        log_info "Building image via ACR Tasks (server-side build)..."
        log_info "  Registry: ${ACR_NAME}"
        log_info "  Image: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
        log_info "  Build context: ${flavor_dir}/"

        az acr build \
            --registry "$ACR_NAME" \
            --image "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" \
            --file "${flavor_dir}/Dockerfile" \
            "${flavor_dir}" \
            --no-logs

        log_success "Docker image built and pushed via ACR Tasks: $image_name"
        return
    fi

    # -------------------------------------------------------------------------
    # Fallback method: Local docker build + push (for local dev with Docker)
    # ORIGINAL CODE (preserved, not deleted — GAP #10 commentary):
    # This was the only build path before. Kept for local development where
    # Docker Desktop or Docker Engine is available.
    # -------------------------------------------------------------------------
    # log_info "Logging in to ACR..."
    # az acr login --name "$ACR_NAME" --output none
    #
    # log_info "Building Docker image: $image_name"
    # docker build -t "$image_name" "${flavor_dir}" --no-cache
    #
    # log_info "Pushing image to ACR..."
    # docker push "$image_name"
    #
    # log_success "Docker image pushed: $image_name"

    log_error "Neither Azure CLI nor Docker found. Cannot build image."
    log_info "Install Azure CLI: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
    log_info "Or use Azure Cloud Shell (pre-authenticated, no install needed)"
    return 1
}

################################################################################
# Apply Kubernetes Manifests
################################################################################

apply_kubernetes_manifests() {
    log_section "Applying Kubernetes Manifests"

    if [[ ! -d "$K8S_MANIFESTS_DIR" ]]; then
        log_error "Kubernetes manifests directory not found: $K8S_MANIFESTS_DIR"
        exit 1
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would apply manifests from $K8S_MANIFESTS_DIR"
        log_verbose "Files to apply:"
        find "$K8S_MANIFESTS_DIR" -name "*.yaml" | sort | while read -r file; do
            log_verbose "  - $file"
        done
        return
    fi

    # Ensure namespace exists first
    log_info "Creating namespace..."
    kubectl apply -f "$K8S_MANIFESTS_DIR/namespace.yaml" --output=none

    # Apply other manifests in order
    local manifest_order=(
        "configmap.yaml"
        "secrets.yaml"
        "deployment.yaml"
        "service.yaml"
        "hpa.yaml"
        "ingress.yaml"
    )

    for manifest in "${manifest_order[@]}"; do
        local manifest_path="$K8S_MANIFESTS_DIR/$manifest"
        if [[ -f "$manifest_path" ]]; then
            log_info "Applying: $manifest"
            kubectl apply -f "$manifest_path" --output=none
        fi
    done

    log_success "All Kubernetes manifests applied"
}

################################################################################
# Wait for Deployment Rollout
################################################################################

wait_for_deployment() {
    log_section "Waiting for Deployment Rollout"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_verbose "DRY RUN: Would wait for rollout"
        return
    fi

    log_info "Waiting for deployment to be ready (timeout: 5 minutes)..."

    if kubectl rollout status deployment/"$APP_NAME" \
        --namespace "$K8S_NAMESPACE" \
        --timeout=5m; then
        log_success "Deployment rolled out successfully"
    else
        log_error "Deployment rollout timed out"
        log_info "Check status with:"
        log_info "  kubectl describe deployment $APP_NAME -n $K8S_NAMESPACE"
        log_info "  kubectl logs -n $K8S_NAMESPACE -l app=ants,component=$APP_NAME"
        exit 1
    fi
}

################################################################################
# Print Access Information
################################################################################

print_access_info() {
    log_section "Deployment Information"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN MODE - No resources deployed"
        return
    fi

    # Get service info
    local svc_info
    svc_info=$(kubectl get svc capital-markets-api -n "$K8S_NAMESPACE" -o json 2>/dev/null || echo "{}")

    # Get pod info
    local pods
    pods=$(kubectl get pods -n "$K8S_NAMESPACE" -l app=ants,component="$APP_NAME" -o json 2>/dev/null || echo "{}")

    cat <<EOF

${GREEN}Deployment Summary:${NC}

  AKS Cluster:      $AKS_NAME
  Resource Group:   $RG
  Location:         $LOCATION
  Namespace:        $K8S_NAMESPACE
  ACR:              $ACR_NAME.azurecr.io

${GREEN}Service Information:${NC}

  Service Name:     capital-markets-api
  Service Port:     8000
  Service Type:     ClusterIP

${GREEN}Useful kubectl Commands:${NC}

  # View deployment status
  kubectl get deployment -n $K8S_NAMESPACE
  kubectl describe deployment $APP_NAME -n $K8S_NAMESPACE

  # View pods
  kubectl get pods -n $K8S_NAMESPACE
  kubectl describe pod -n $K8S_NAMESPACE -l app=ants

  # View logs
  kubectl logs -n $K8S_NAMESPACE -l app=ants,component=$APP_NAME -f
  kubectl logs -n $K8S_NAMESPACE -l app=ants,component=$APP_NAME --tail=100

  # Port forward for local testing
  kubectl port-forward -n $K8S_NAMESPACE svc/capital-markets-api 8000:8000

  # Access shell
  kubectl exec -it -n $K8S_NAMESPACE <pod-name> -- /bin/bash

${GREEN}ACR Commands:${NC}

  # View images
  az acr repository list --name $ACR_NAME
  az acr repository show-tags --name $ACR_NAME --repository $DOCKER_IMAGE_NAME

  # Login to ACR
  az acr login --name $ACR_NAME

${GREEN}Cleanup:${NC}

  # Destroy only ANTS resources
  ./infra/deploy-lab.sh --destroy

EOF
}

################################################################################
# Destroy Resources
################################################################################

destroy_resources() {
    log_section "Destroying ANTS Resources"

    log_warning "This will delete resources tagged with project=$PROJECT_TAG"
    log_warning "Resources in resource group: $RG"

    # List resources to be deleted
    log_info "Resources tagged with project=$PROJECT_TAG:"

    local acr_exists_check
    acr_exists_check=$(az acr list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].name" -o tsv 2>/dev/null || echo "")

    local aks_exists_check
    aks_exists_check=$(az aks list -g "$RG" --query "[?tags.project=='$PROJECT_TAG'].name" -o tsv 2>/dev/null || echo "")

    if [[ -n "$acr_exists_check" ]]; then
        log_info "  - ACR: $acr_exists_check"
    fi

    if [[ -n "$aks_exists_check" ]]; then
        log_info "  - AKS: $aks_exists_check"
    fi

    if [[ -z "$acr_exists_check" && -z "$aks_exists_check" ]]; then
        log_warning "No resources found with project=$PROJECT_TAG"
        return
    fi

    if ! confirm "Are you sure you want to delete these resources?"; then
        log_warning "Deletion cancelled"
        return
    fi

    # Delete AKS cluster
    if [[ -n "$aks_exists_check" ]]; then
        log_info "Deleting AKS cluster: $aks_exists_check"
        az aks delete \
            --resource-group "$RG" \
            --name "$aks_exists_check" \
            --no-wait \
            --yes \
            --output none
        log_success "AKS cluster deletion initiated (background)"
    fi

    # Delete ACR
    if [[ -n "$acr_exists_check" ]]; then
        log_info "Deleting ACR: $acr_exists_check"
        az acr delete \
            --resource-group "$RG" \
            --name "$acr_exists_check" \
            --yes \
            --output none
        log_success "ACR deleted"
    fi

    log_success "Cleanup initiated"
}

################################################################################
# Main Execution
################################################################################

print_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

ANTS Capital Markets Lab Deployment Script

OPTIONS:
  --dry-run         Show what would be deployed without making changes
  --destroy         Destroy ANTS resources (keeps resource group intact)
  --verbose         Enable verbose output
  --help            Show this help message

EXAMPLES:
  # Deploy to lab environment
  $0

  # Preview deployment
  $0 --dry-run

  # Destroy all ANTS resources
  $0 --destroy

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --destroy)
                DESTROY=true
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
    log_section "ANTS Capital Markets - Lab Deployment"

    parse_arguments "$@"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No resources will be created or modified"
    fi

    # Always run prerequisite checks
    check_prerequisites
    verify_azure_context

    if [[ "$DESTROY" == "true" ]]; then
        destroy_resources
        exit 0
    fi

    # Deployment flow
    estimate_monthly_cost

    if ! confirm "Proceed with deployment?"; then
        log_warning "Deployment cancelled"
        exit 0
    fi

    create_networking
    create_aks_cluster
    create_acr
    attach_acr_to_aks
    get_aks_credentials
    build_and_push_image
    apply_kubernetes_manifests
    wait_for_deployment
    print_access_info

    log_success "Deployment complete!"
}

# Run main function
main "$@"
