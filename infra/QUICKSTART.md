# ANTS Capital Markets - Quick Start Guide

## 30-Second Setup

```bash
# 1. Prerequisites installed? (az, kubectl, docker)
az --version

# 2. Login to Azure
az login

# 3. Deploy everything in one command
cd /path/to/AscendERP
./infra/deploy-lab.sh

# 4. Wait for rollout (5 minutes)
# Script will print access URLs when complete
```

## 5-Minute Verification

```bash
# Check deployment status
kubectl get deployment -n ants-capital-markets

# View pods
kubectl get pods -n ants-capital-markets

# Check logs
kubectl logs -n ants-capital-markets -l app=ants -f

# Test health endpoint
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000 &
curl http://localhost:8000/health
```

## Common Commands

### Deployment Management

```bash
# Deploy
./infra/deploy-lab.sh

# Preview (dry-run)
./infra/deploy-lab.sh --dry-run

# Destroy
./infra/deploy-lab.sh --destroy

# Teardown with confirmation
./infra/teardown-lab.sh
```

### Kubernetes Operations

```bash
# Get status
kubectl get all -n ants-capital-markets

# View details
kubectl describe deployment capital-markets-api -n ants-capital-markets

# View logs
kubectl logs -n ants-capital-markets -l component=capital-markets-api -f

# Port forward
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000

# Exec into pod
kubectl exec -it <pod-name> -n ants-capital-markets -- /bin/bash

# Scale manually
kubectl scale deployment capital-markets-api --replicas=3 -n ants-capital-markets
```

### Configuration Management

```bash
# View ConfigMap
kubectl get configmap -n ants-capital-markets

# Edit ConfigMap
kubectl edit configmap ants-cm-config -n ants-capital-markets

# View Secrets (masked)
kubectl get secret -n ants-capital-markets
```

### Azure Operations

```bash
# Check AKS
az aks show -g DNvidiaBTANF -n ants-cm-lab-aks

# Check ACR
az acr show -g DNvidiaBTANF -n antslab

# List repositories
az acr repository list --name antslab

# View images
az acr repository show-tags --name antslab --repository ants-capital-markets
```

## Troubleshooting

### Pod won't start?

```bash
# Check events
kubectl describe pod <pod-name> -n ants-capital-markets

# View logs
kubectl logs <pod-name> -n ants-capital-markets

# Check resources
kubectl top nodes
kubectl describe nodes
```

### Lost connection?

```bash
# Re-authenticate
az login

# Get credentials again
az aks get-credentials -g DNvidiaBTANF -n ants-cm-lab-aks --overwrite-existing
```

### Image pull errors?

```bash
# Check if image exists
az acr repository show-tags --name antslab --repository ants-capital-markets

# Rebuild and push
docker build -t antslab.azurecr.io/ants-capital-markets:latest .
docker push antslab.azurecr.io/ants-capital-markets:latest
```

## File Locations

```
/path/to/AscendERP/infra/
├── deploy-lab.sh              # Main deployment script
├── teardown-lab.sh            # Cleanup script
├── README-DEPLOYMENT.md       # Full documentation
├── QUICKSTART.md              # This file
└── k8s/capital-markets/       # Kubernetes manifests
    ├── namespace.yaml
    ├── configmap.yaml
    ├── secrets.yaml
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    └── hpa.yaml
```

## Important Notes

- Resource Group: `DNvidiaBTANF` (SHARED - do NOT modify)
- Only ANTS resources are tagged with `project=ants-capital-markets`
- Teardown script only deletes ANTS resources, never touches other RG resources
- Secrets file contains PLACEHOLDERS - update before running!
- Lab sizing: 2 nodes (Standard_B2ms), scales to max 3 replicas

## Next Steps

1. Read full documentation: `README-DEPLOYMENT.md`
2. Customize configuration in `infra/k8s/capital-markets/configmap.yaml`
3. Update secrets in `infra/k8s/capital-markets/secrets.yaml`
4. Run deployment: `./infra/deploy-lab.sh`
5. Monitor with: `kubectl get pods -n ants-capital-markets --watch`

## Support

For issues, check:
1. Pod logs: `kubectl logs -n ants-capital-markets -l app=ants`
2. Events: `kubectl describe pod <name> -n ants-capital-markets`
3. Full docs: `README-DEPLOYMENT.md`
