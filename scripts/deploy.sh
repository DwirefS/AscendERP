#!/bin/bash

#
# ANTS Platform Deployment Script
#
# Automates deployment of ANTS platform to Azure Kubernetes Service (AKS)
#
# Usage:
#   ./scripts/deploy.sh [environment] [options]
#
# Environments:
#   dev         - Development environment (local/minikube)
#   staging     - Staging environment
#   production  - Production environment
#
# Options:
#   --dry-run          - Show what would be deployed without applying
#   --skip-tests       - Skip pre-deployment tests
#   --skip-backup      - Skip backup creation
#   --force            - Force deployment without confirmations
#   --rollback         - Rollback to previous deployment
#   --version VERSION  - Deploy specific version
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HELM_CHART_DIR="$PROJECT_ROOT/infra/helm"

# Default values
ENVIRONMENT="${1:-dev}"
DRY_RUN=false
SKIP_TESTS=false
SKIP_BACKUP=false
FORCE=false
ROLLBACK=false
VERSION="${VERSION:-latest}"

# Parse options
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

confirm() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi

    read -p "$1 (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Deployment cancelled"
        exit 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi

    # Check helm
    if ! command -v helm &> /dev/null; then
        log_error "helm not found. Please install helm."
        exit 1
    fi

    # Check Azure CLI for non-dev deployments
    if [[ "$ENVIRONMENT" != "dev" ]] && ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install Azure CLI."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

set_kubernetes_context() {
    log_info "Setting Kubernetes context for $ENVIRONMENT..."

    case $ENVIRONMENT in
        dev)
            kubectl config use-context docker-desktop || \
            kubectl config use-context minikube || {
                log_error "No local Kubernetes context found"
                exit 1
            }
            NAMESPACE="ants-dev"
            ;;
        staging)
            az aks get-credentials \
                --resource-group ants-staging-rg \
                --name ants-staging \
                --overwrite-existing
            NAMESPACE="ants-staging"
            ;;
        production)
            az aks get-credentials \
                --resource-group ants-production-rg \
                --name ants-production \
                --overwrite-existing
            NAMESPACE="ants-production"
            ;;
        *)
            log_error "Unknown environment: $ENVIRONMENT"
            exit 1
            ;;
    esac

    # Create namespace if it doesn't exist
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

    log_success "Kubernetes context set to $ENVIRONMENT ($NAMESPACE)"
}

run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_warning "Skipping tests (--skip-tests)"
        return 0
    fi

    log_info "Running pre-deployment tests..."

    cd "$PROJECT_ROOT"

    # Run unit tests
    pytest tests/unit/ -v --tb=short || {
        log_error "Unit tests failed"
        exit 1
    }

    # Run integration tests for staging/production
    if [[ "$ENVIRONMENT" != "dev" ]]; then
        pytest tests/integration/ -v --tb=short || {
            log_error "Integration tests failed"
            exit 1
        }
    fi

    log_success "Tests passed"
}

create_backup() {
    if [[ "$SKIP_BACKUP" == "true" ]] || [[ "$ENVIRONMENT" == "dev" ]]; then
        log_warning "Skipping backup"
        return 0
    fi

    log_info "Creating backup of current deployment..."

    BACKUP_DIR="$PROJECT_ROOT/backups/${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup Helm values
    helm get values ants-core -n $NAMESPACE > "$BACKUP_DIR/helm-values.yaml" 2>/dev/null || true

    # Backup Kubernetes resources
    kubectl get all -n $NAMESPACE -o yaml > "$BACKUP_DIR/kubernetes-resources.yaml" 2>/dev/null || true

    # Backup database (optional, requires database tools)
    # pg_dump ... > "$BACKUP_DIR/database.sql"

    log_success "Backup created at $BACKUP_DIR"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure components..."

    # Deploy infrastructure with Helm
    HELM_ARGS=(
        --namespace $NAMESPACE
        --create-namespace
        --set environment=$ENVIRONMENT
        --values "$HELM_CHART_DIR/values-$ENVIRONMENT.yaml"
    )

    if [[ "$VERSION" != "latest" ]]; then
        HELM_ARGS+=(--set image.tag=$VERSION)
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        HELM_ARGS+=(--dry-run --debug)
    fi

    # Deploy core ANTS platform
    log_info "Deploying ANTS core..."
    helm upgrade --install ants-core "$HELM_CHART_DIR/ants-core" "${HELM_ARGS[@]}"

    # Deploy observability stack
    log_info "Deploying observability stack..."
    helm upgrade --install ants-observability "$HELM_CHART_DIR/ants-observability" "${HELM_ARGS[@]}"

    # Deploy NIM microservices
    if [[ "$ENVIRONMENT" != "dev" ]]; then
        log_info "Deploying NVIDIA NIM..."
        helm upgrade --install ants-nim "$HELM_CHART_DIR/ants-nim" "${HELM_ARGS[@]}"
    fi

    log_success "Infrastructure deployed"
}

wait_for_deployment() {
    log_info "Waiting for deployments to be ready..."

    # Wait for core services
    kubectl wait --for=condition=ready pod \
        -l app=ants-api-gateway \
        -n $NAMESPACE \
        --timeout=600s || {
            log_error "Deployment timeout"
            return 1
        }

    kubectl wait --for=condition=ready pod \
        -l app=ants-orchestrator \
        -n $NAMESPACE \
        --timeout=600s || {
            log_error "Deployment timeout"
            return 1
        }

    log_success "Deployments ready"
}

run_health_checks() {
    log_info "Running health checks..."

    # Get API Gateway endpoint
    if [[ "$ENVIRONMENT" == "dev" ]]; then
        API_ENDPOINT="http://localhost:8080"
    else
        API_ENDPOINT=$(kubectl get service ants-api-gateway -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
        API_ENDPOINT="http://$API_ENDPOINT"
    fi

    # Health check
    max_retries=30
    retry=0
    while [[ $retry -lt $max_retries ]]; do
        if curl -f -s "$API_ENDPOINT/health" > /dev/null; then
            log_success "Health check passed"
            return 0
        fi
        retry=$((retry + 1))
        log_info "Waiting for service... ($retry/$max_retries)"
        sleep 10
    done

    log_error "Health check failed"
    return 1
}

rollback_deployment() {
    log_warning "Rolling back deployment..."

    helm rollback ants-core -n $NAMESPACE || {
        log_error "Rollback failed"
        exit 1
    }

    log_success "Rollback completed"
}

print_deployment_info() {
    log_success "Deployment completed successfully!"
    echo ""
    echo "========================================"
    echo "  ANTS Platform - Deployment Summary"
    echo "========================================"
    echo "Environment:  $ENVIRONMENT"
    echo "Namespace:    $NAMESPACE"
    echo "Version:      $VERSION"
    echo ""
    echo "Services:"
    kubectl get services -n $NAMESPACE
    echo ""
    echo "Pods:"
    kubectl get pods -n $NAMESPACE
    echo ""
    echo "========================================"

    if [[ "$ENVIRONMENT" == "dev" ]]; then
        echo ""
        echo "Access the platform:"
        echo "  API Gateway:  http://localhost:8080"
        echo "  DevUI:        http://localhost:8090"
        echo "  Grafana:      http://localhost:3000"
        echo ""
    fi
}

# Main execution
main() {
    echo "========================================"
    echo "  ANTS Platform Deployment"
    echo "========================================"
    echo "Environment: $ENVIRONMENT"
    echo "Version:     $VERSION"
    echo "Dry Run:     $DRY_RUN"
    echo "========================================"
    echo ""

    if [[ "$ROLLBACK" == "true" ]]; then
        confirm "Are you sure you want to rollback $ENVIRONMENT?"
        check_prerequisites
        set_kubernetes_context
        rollback_deployment
        exit 0
    fi

    confirm "Deploy ANTS platform to $ENVIRONMENT?"

    check_prerequisites
    set_kubernetes_context
    run_tests
    create_backup
    deploy_infrastructure

    if [[ "$DRY_RUN" == "false" ]]; then
        wait_for_deployment
        run_health_checks
        print_deployment_info
    else
        log_info "Dry run completed - no changes applied"
    fi
}

# Run main
main
