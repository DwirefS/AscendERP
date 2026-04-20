# ANTS Capital Markets - Lab Deployment Guide

## Overview

This directory contains all necessary infrastructure-as-code for deploying the ANTS Capital Markets multi-agent platform to Azure Kubernetes Service (AKS) in the shared lab environment.

**Resource Group:** `DNvidiaBTANF` (SHARED - lab environment)

## Directory Structure

```
infra/
├── deploy-lab.sh                    # Main deployment script (ALL-IN-ONE)
├── teardown-lab.sh                  # Safe resource cleanup script
├── README-DEPLOYMENT.md             # This file
└── k8s/
    └── capital-markets/             # Kubernetes manifests
        ├── namespace.yaml           # Namespace definition
        ├── configmap.yaml           # Configuration data
        ├── secrets.yaml             # Secret templates (NEVER commit real values!)
        ├── deployment.yaml          # Pod deployment & service account
        ├── service.yaml             # ClusterIP service
        ├── ingress.yaml             # Ingress routing
        └── hpa.yaml                 # Horizontal Pod Autoscaler
```

## Quick Start

### Prerequisites

Install the required tools:

```bash
# macOS
brew install azure-cli kubernetes-cli docker helm

# Linux (Ubuntu/Debian)
sudo apt-get install -y azure-cli kubectl docker.io
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Windows
# Use choco or download from official sources
choco install azure-cli kubernetes-cli docker-desktop
```

### Deployment (One Command)

```bash
# Preview deployment (dry-run)
./infra/deploy-lab.sh --dry-run

# Deploy to lab
./infra/deploy-lab.sh

# With verbose output
./infra/deploy-lab.sh --verbose
```

That's it! The script handles:
1. ✓ Prerequisite checks (az, kubectl, docker, helm)
2. ✓ Azure account verification
3. ✓ AKS cluster creation (if needed)
4. ✓ ACR creation (if needed)
5. ✓ ACR-to-AKS integration
6. ✓ Docker image build & push
7. ✓ Kubernetes manifests application
8. ✓ Deployment rollout verification
9. ✓ Access information printing

## Kubernetes Manifests

### 1. Namespace (`namespace.yaml`)

Isolates ANTS resources with metadata labels:

```yaml
namespace: ants-capital-markets
labels:
  app: ants
  flavor: capital-markets
  environment: lab
  project: ants-capital-markets
```

### 2. ConfigMap (`configmap.yaml`)

Contains application configuration:

- **Environment Variables:**
  - `LOG_LEVEL`: Set to "INFO" (INFO, DEBUG, WARN, ERROR)
  - `ENVIRONMENT`: Set to "lab"
  - `FLAVOR`: Set to "capital-markets"
  - `API_PORT`: 8000
  - `WORKERS`: 4

- **Configuration Files:**
  - `agents_config.yaml`: Agent definitions (market_analyst, risk_manager, execution_manager)
  - `councils_config.yaml`: Council/voting bodies and decision thresholds
  - `models_config.yaml`: LLM model configurations

### 3. Secrets (`secrets.yaml`)

**IMPORTANT:** This file contains PLACEHOLDER values. Never commit real secrets!

```yaml
DATABASE_URL: "postgresql://user:PASSWORD_PLACEHOLDER@..."
OPENAI_API_KEY: "sk-PLACEHOLDER_OPENAI_API_KEY"
AZURE_KEY_VAULT_URI: "https://PLACEHOLDER-kv.vault.azure.net/"
JWT_SECRET: "PLACEHOLDER_JWT_SECRET_MIN_32_CHARS_LONG"
RABBITMQ_URL: "amqp://user:PASSWORD_PLACEHOLDER@..."
```

**Recommended:** Use Azure Key Vault + CSI Driver for production secrets.

### 4. Deployment (`deployment.yaml`)

Pod deployment specification:

- **Replicas:** 1 (lab sizing - can scale to 3 with HPA)
- **Image:** `${ACR_NAME}.azurecr.io/ants-capital-markets:latest`
- **Resource Requests:** 250m CPU, 512Mi memory
- **Resource Limits:** 500m CPU, 1Gi memory
- **Probes:**
  - Liveness: `/health` (detect dead pods)
  - Readiness: `/ready` (traffic control)
  - Startup: `/health` (warm-up time)
- **Security:** Non-root user (UID 1000), read-only root filesystem
- **Volumes:** ConfigMap mounts, ephemeral logs storage

### 5. Service (`service.yaml`)

Internal ClusterIP service:

```yaml
service: capital-markets-api
port: 8000
type: ClusterIP
```

### 6. Ingress (`ingress.yaml`)

Routes external traffic:

```
/health     → capital-markets-api:8000
/ready      → capital-markets-api:8000
/api/v1/*   → capital-markets-api:8000
```

**Note:** TLS certificates are placeholders (self-signed). Replace for production.

### 7. HPA (`hpa.yaml`)

Horizontal Pod Autoscaler:

- **Min Replicas:** 1
- **Max Replicas:** 3
- **Scaling Trigger:** 70% CPU utilization
- **Memory Trigger:** 80% memory utilization

## Deployment Script Details

### `deploy-lab.sh` Features

```bash
#!/bin/bash
# Configuration (hardcoded safe defaults for lab)
RG="DNvidiaBTANF"              # Resource group (NEVER CHANGE)
AKS_NAME="ants-cm-lab-aks"     # Cluster name
ACR_NAME="antslab"              # Registry name
AKS_VM_SKU="Standard_B2ms"      # Lab-appropriate VM
AKS_NODE_COUNT="2"              # 2 nodes

# Project tagging (for safe cleanup)
PROJECT_TAG="ants-capital-markets"
```

### Script Workflow

1. **Prerequisite Checks**
   - Azure CLI, kubectl, docker, helm installed?
   - Version information displayed

2. **Azure Verification**
   - Logged into Azure?
   - Correct subscription/RG?

3. **Cost Estimation**
   - Shows estimated monthly cost: $150-200 USD
   - Breakdown by resource

4. **Resource Creation**
   - Creates AKS cluster (with confirmation, 10-15 min)
   - Creates ACR (with confirmation)
   - Attaches ACR to AKS for image pulling

5. **Image Pipeline**
   - Authenticates to ACR
   - Builds Docker image
   - Pushes to registry

6. **Kubernetes Deployment**
   - Applies namespace
   - Applies ConfigMap
   - Applies Secrets
   - Applies Deployment
   - Applies Service
   - Applies HPA
   - Applies Ingress

7. **Verification**
   - Waits for rollout (5 min timeout)
   - Prints access information

### Script Options

```bash
./infra/deploy-lab.sh              # Full deployment with prompts
./infra/deploy-lab.sh --dry-run    # Preview (no changes)
./infra/deploy-lab.sh --verbose    # Extra logging
./infra/deploy-lab.sh --destroy    # Remove ONLY ANTS resources
./infra/deploy-lab.sh --help       # Show usage
```

## Teardown Script

### `teardown-lab.sh` Features

**Guarantees:**
- ✓ Only deletes resources tagged with `project=ants-capital-markets`
- ✓ Does NOT delete the resource group
- ✓ Does NOT touch other resources in the RG
- ✓ Requires explicit confirmation (twice!)

### Usage

```bash
./infra/teardown-lab.sh           # Interactive with confirmations
./infra/teardown-lab.sh --force   # Skip confirmations
./infra/teardown-lab.sh --verbose # Detailed logging
```

### What Gets Deleted

- AKS clusters tagged with `project=ants-capital-markets`
- Container registries tagged with `project=ants-capital-markets`
- Associated managed disks
- Associated network interfaces
- Associated network security groups

### What Stays

- Resource group `DNvidiaBTANF` (untouched)
- Other resources in the RG
- All shared infrastructure

## Post-Deployment

### Access the API

```bash
# Port-forward for local testing
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000

# Test health endpoint
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Monitor Deployment

```bash
# View deployment status
kubectl get deployment -n ants-capital-markets
kubectl describe deployment capital-markets-api -n ants-capital-markets

# View pods
kubectl get pods -n ants-capital-markets
kubectl logs -n ants-capital-markets -l app=ants,component=capital-markets-api -f

# Watch real-time
kubectl get pods -n ants-capital-markets --watch
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment capital-markets-api --replicas=3 -n ants-capital-markets

# Check HPA status
kubectl get hpa -n ants-capital-markets
kubectl describe hpa capital-markets-api-hpa -n ants-capital-markets
```

### View Configurations

```bash
# ConfigMap
kubectl get configmap -n ants-capital-markets
kubectl describe configmap ants-cm-config -n ants-capital-markets

# Secrets (be careful!)
kubectl get secret -n ants-capital-markets
```

## Troubleshooting

### Pod won't start

```bash
# Check events
kubectl describe pod <pod-name> -n ants-capital-markets

# View logs
kubectl logs <pod-name> -n ants-capital-markets

# Check resource availability
kubectl top nodes
kubectl describe nodes
```

### Image pull errors

```bash
# Verify ACR attachment
az role assignment list --assignee <kubelet-identity> --scope <acr-id>

# Check image exists
az acr repository show-tags --name antslab --repository ants-capital-markets

# Manually pull to test
docker pull antslab.azurecr.io/ants-capital-markets:latest
```

### Deployment stuck in pending

```bash
# Check node resources
kubectl describe nodes

# Check resource requests/limits
kubectl describe deployment capital-markets-api -n ants-capital-markets

# May need to increase AKS node count
az aks scale --resource-group DNvidiaBTANF --name ants-cm-lab-aks --node-count 3
```

### Access denied errors

```bash
# Verify subscription/RG
az account show
az group show -n DNvidiaBTANF

# Verify kubeconfig
kubectl cluster-info
kubectl auth can-i get pods --as=system:serviceaccount:ants-capital-markets:ants-cm-sa
```

## Cost Management

### Current Monthly Estimates

| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| AKS Nodes (2x) | Standard_B2ms | $80-100 |
| ACR | Basic | $40-50 |
| Bandwidth/Storage | - | $30-50 |
| **Total** | - | **$150-200** |

### Cost Optimization Tips

1. **Stop when not in use:**
   ```bash
   # Scale down to 0 replicas (if no traffic needed)
   kubectl scale deployment capital-markets-api --replicas=0

   # Or use teardown script to delete resources entirely
   ./infra/teardown-lab.sh
   ```

2. **Monitor resource usage:**
   ```bash
   # AKS metrics
   kubectl top nodes
   kubectl top pods -n ants-capital-markets
   ```

3. **Use Azure cost calculator:**
   - https://azure.microsoft.com/en-us/pricing/calculator/

## Secrets Management (Best Practices)

### Current Approach (for lab/testing)

1. Placeholder secrets in `secrets.yaml`
2. Edit before applying:
   ```bash
   # Option 1: Edit YAML directly
   vim infra/k8s/capital-markets/secrets.yaml

   # Option 2: Set via kubectl
   kubectl set env deployment/capital-markets-api \
     DATABASE_URL="postgresql://..." \
     OPENAI_API_KEY="sk-..." \
     -n ants-capital-markets
   ```

### Production Approach (Recommended)

1. **Use Azure Key Vault:**
   ```bash
   # Create Key Vault
   az keyvault create -n ants-cm-kv -g DNvidiaBTANF

   # Store secrets
   az keyvault secret set -n db-connection-string --vault-name ants-cm-kv --value "postgresql://..."
   ```

2. **Enable CSI Driver:**
   ```bash
   # AKS already has CSI driver support
   # Enable in ingress.yaml (commented section)
   # Reference secrets from Key Vault
   ```

3. **Use Azure AD Service Principal:**
   - Pod identity with system-assigned managed identity
   - Automatic secret rotation

## Security Considerations

### Current Deployment

- ✓ Non-root container user (UID 1000)
- ✓ Read-only root filesystem (where possible)
- ✓ Network policies not enforced (lab)
- ✓ TLS placeholders (replace for production)
- ✓ RBAC with service account

### Production Hardening

1. **Network Security:**
   ```bash
   # Enable Azure Network Policy
   az aks update --name ants-cm-lab-aks -g DNvidiaBTANF --network-policy azure
   ```

2. **Secrets Management:**
   - Use Azure Key Vault + CSI driver
   - Never commit real secrets to git
   - Rotate secrets regularly

3. **Image Security:**
   - Enable ACR image scanning
   - Use image signatures
   - Scan for vulnerabilities

4. **RBAC:**
   - Limit service account permissions
   - Use Pod Security Policies
   - Implement admission controllers

## Advanced Topics

### Custom Configuration

Edit the ConfigMap for your use case:

```bash
# Edit live
kubectl edit configmap ants-cm-config -n ants-capital-markets

# Update agents
kubectl set env configmap/ants-cm-config \
  agents_enabled="market_analyst,risk_manager,execution_manager" \
  -n ants-capital-markets
```

### Monitoring & Observability

Add Prometheus/Grafana:

```bash
# Install Prometheus Helm chart
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus -n monitoring --create-namespace
```

### CI/CD Integration

Integrate with GitHub Actions:

```yaml
# .github/workflows/deploy.yml
name: Deploy to AKS
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy
        run: ./infra/deploy-lab.sh
```

## Support & Issues

### Getting Help

1. Check pod logs:
   ```bash
   kubectl logs -n ants-capital-markets -l app=ants
   ```

2. Verify manifests:
   ```bash
   kubectl describe all -n ants-capital-markets
   ```

3. Check Azure resources:
   ```bash
   az aks show -g DNvidiaBTANF -n ants-cm-lab-aks
   az acr show -g DNvidiaBTANF -n antslab
   ```

## References

- [Azure AKS Documentation](https://learn.microsoft.com/en-us/azure/aks/)
- [Kubernetes Official Docs](https://kubernetes.io/docs/)
- [Helm Charts](https://artifacthub.io/)
- [Azure CLI Reference](https://learn.microsoft.com/en-us/cli/azure/)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-04 | Initial deployment manifests and scripts |

---

**Last Updated:** 2026-03-04
**Environment:** Azure Lab (DNvidiaBTANF)
**Status:** Ready for Production-like Testing
