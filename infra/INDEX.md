# ANTS Capital Markets - Infrastructure Files Index

**Created:** 2026-03-04
**Environment:** Azure Lab (DNvidiaBTANF)
**Status:** Ready for Deployment

## Quick Links

- **Start Here:** [QUICKSTART.md](QUICKSTART.md) - 30-second setup guide
- **Full Guide:** [README-DEPLOYMENT.md](README-DEPLOYMENT.md) - Comprehensive documentation
- **Pre-Deploy:** [DEPLOYMENT-CHECKLIST.md](DEPLOYMENT-CHECKLIST.md) - Complete verification checklist

## File Organization

```
infra/
├── deploy-lab.sh                      # Main deployment script (run this first)
├── teardown-lab.sh                    # Cleanup script (safe removal only)
├── INDEX.md                           # This file
├── QUICKSTART.md                      # 30-second setup
├── README-DEPLOYMENT.md               # Full documentation
├── DEPLOYMENT-CHECKLIST.md            # Pre/post deployment checks
└── k8s/
    └── capital-markets/
        ├── namespace.yaml             # Kubernetes namespace
        ├── configmap.yaml             # Configuration data
        ├── secrets.yaml               # Secret templates (PLACEHOLDERS!)
        ├── deployment.yaml            # Pod deployment spec
        ├── service.yaml               # Internal service
        ├── ingress.yaml               # External routing
        └── hpa.yaml                   # Auto-scaling rules
```

## Files at a Glance

### Kubernetes Manifests (7 files, 505 lines)

| File | Size | Purpose |
|------|------|---------|
| **namespace.yaml** | 9 lines | Create `ants-capital-markets` namespace with labels |
| **configmap.yaml** | 78 lines | Application configuration (env vars, agent/council/model configs) |
| **secrets.yaml** | 64 lines | Secret template with PLACEHOLDER values (never commit real secrets!) |
| **deployment.yaml** | 158 lines | Pod deployment, ServiceAccount, security context, health checks |
| **service.yaml** | 26 lines | ClusterIP service on port 8000 |
| **ingress.yaml** | 114 lines | NGINX ingress with paths, TLS placeholder, rate limiting |
| **hpa.yaml** | 56 lines | Horizontal Pod Autoscaler (1-3 replicas, 70% CPU trigger) |

### Deployment Automation (2 scripts, 1,142 lines)

| Script | Lines | Purpose |
|--------|-------|---------|
| **deploy-lab.sh** | 696 | Complete deployment script - creates AKS, ACR, builds image, deploys manifests |
| **teardown-lab.sh** | 446 | Safe cleanup - only deletes ANTS-tagged resources, preserves RG |

### Documentation (3 files, 1,155 lines)

| Document | Lines | Purpose |
|----------|-------|---------|
| **README-DEPLOYMENT.md** | 545 | Comprehensive guide with all details, troubleshooting, security |
| **QUICKSTART.md** | 182 | Quick reference with minimal commands |
| **DEPLOYMENT-CHECKLIST.md** | 428 | Step-by-step checklist for pre/during/post deployment |

## Quick Start (Copy & Paste)

```bash
# 1. Navigate to project
cd /path/to/AscendERP

# 2. Preview deployment (no changes)
./infra/deploy-lab.sh --dry-run

# 3. Deploy (with prompts)
./infra/deploy-lab.sh

# 4. Monitor
kubectl get pods -n ants-capital-markets --watch

# 5. Test
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000 &
curl http://localhost:8000/health

# 6. Cleanup (when done)
./infra/teardown-lab.sh
```

## Key Features

### Safety & Reliability
- ✓ Strict bash mode (`set -euo pipefail`)
- ✓ Color-coded output for clarity
- ✓ Explicit confirmation prompts
- ✓ Cost estimates before creation
- ✓ Double-confirmation for destructive ops
- ✓ Dry-run mode for preview
- ✓ Comprehensive error handling
- ✓ Pre-flight checks for all prerequisites

### Resource Management
- ✓ Lab-appropriate sizing (B2ms nodes, Basic ACR)
- ✓ Cost estimated at $150-200/month
- ✓ Auto-scaling from 1 to 3 replicas
- ✓ Project-based tagging for safe cleanup
- ✓ RG-level isolation (shared lab environment)

### Security
- ✓ Non-root container user
- ✓ Read-only root filesystem
- ✓ SecurityContext hardening
- ✓ RBAC with service accounts
- ✓ Secret placeholders (never commit real values!)
- ✓ Network security headers in Ingress
- ✓ CORS configuration
- ✓ Rate limiting on ingress

### Observability
- ✓ Liveness probes (`/health`)
- ✓ Readiness probes (`/ready`)
- ✓ Startup probes with warm-up time
- ✓ Health check endpoints
- ✓ Kubernetes events and logs
- ✓ Resource utilization metrics

## Resource Specifications

### AKS Cluster
- **Node SKU:** Standard_B2ms (burstable, cost-effective)
- **Node Count:** 2
- **Availability:** Single zone (lab appropriate)

### Container
- **CPU Request:** 250m | **Limit:** 500m
- **Memory Request:** 512Mi | **Limit:** 1Gi

### Scaling
- **Min Replicas:** 1
- **Max Replicas:** 3
- **Scaling Trigger:** 70% CPU utilization

### Registry (ACR)
- **SKU:** Basic
- **Storage:** 10 GB included

## Configuration

All resources are tagged with:
```
project=ants-capital-markets    (for cleanup identification)
environment=lab                 (deployment environment)
flavor=capital-markets          (application variant)
managed-by=deploy-lab.sh        (creation method)
```

## Critical Notes

1. **Secrets:** `secrets.yaml` contains PLACEHOLDER values
   - Never commit real secrets to version control
   - Update values before deploying or use Azure Key Vault

2. **Shared Lab:** Resource group `DNvidiaBTANF` is shared
   - Teardown script ONLY deletes ANTS resources
   - Resource group is NEVER deleted
   - Other projects' resources are NOT touched

3. **Ingress:** Uses NGINX controller
   - TLS certificate is placeholder (self-signed for lab)
   - Replace with real certificate for production

4. **Image:** Expects Docker image in ACR
   - Script builds image if Dockerfile exists
   - Otherwise, manual build required

## Deployment Workflow

```
1. Prerequisites Check
   └─ az, kubectl, docker, helm installed?

2. Azure Verification
   └─ Logged in? Correct subscription/RG?

3. Cost Review
   └─ $150-200/month acceptable?

4. Resource Creation
   ├─ AKS cluster (if not exists)
   ├─ ACR (if not exists)
   └─ ACR-to-AKS attachment

5. Image Pipeline
   ├─ Docker build (if Dockerfile exists)
   └─ Docker push to ACR

6. Kubernetes Deployment
   ├─ Apply namespace
   ├─ Apply ConfigMap
   ├─ Apply Secrets
   ├─ Apply Deployment
   ├─ Apply Service
   ├─ Apply HPA
   └─ Apply Ingress

7. Verification
   └─ Wait for rollout (5 min timeout)

8. Access Information
   └─ Print URLs and commands
```

## Common Operations

### Deploy
```bash
./infra/deploy-lab.sh
```

### Preview (Dry-Run)
```bash
./infra/deploy-lab.sh --dry-run
```

### Verbose Logging
```bash
./infra/deploy-lab.sh --verbose
```

### Cleanup
```bash
./infra/teardown-lab.sh
```

### Monitor
```bash
kubectl get pods -n ants-capital-markets --watch
kubectl logs -n ants-capital-markets -l app=ants -f
```

### Port Forward
```bash
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000
```

## Troubleshooting

### Pod won't start?
1. Check events: `kubectl describe pod <name> -n ants-capital-markets`
2. View logs: `kubectl logs <name> -n ants-capital-markets`
3. Check node resources: `kubectl top nodes`

### Image pull errors?
1. Verify image exists: `az acr repository show-tags --name antslab --repository ants-capital-markets`
2. Check ACR-AKS attachment
3. Rebuild image if needed

### Lost Azure connection?
1. Re-login: `az login`
2. Get credentials: `az aks get-credentials -g DNvidiaBTANF -n ants-cm-lab-aks --overwrite-existing`

See `README-DEPLOYMENT.md` for comprehensive troubleshooting guide.

## Documentation Map

- **Getting Started:** QUICKSTART.md
- **Setup & Deployment:** README-DEPLOYMENT.md (Quick Start section)
- **Manifest Details:** README-DEPLOYMENT.md (Kubernetes Manifests section)
- **Script Details:** README-DEPLOYMENT.md (Script Details section)
- **Post-Deployment:** README-DEPLOYMENT.md (Post-Deployment section)
- **Monitoring:** README-DEPLOYMENT.md (Post-Deployment → Monitor section)
- **Troubleshooting:** README-DEPLOYMENT.md (Troubleshooting section)
- **Pre-Deployment:** DEPLOYMENT-CHECKLIST.md (Pre-Deployment Checklist)
- **Verification:** DEPLOYMENT-CHECKLIST.md (Post-Deployment Verification)
- **Secrets:** README-DEPLOYMENT.md (Secrets Management section)
- **Security:** README-DEPLOYMENT.md (Security Considerations section)

## Version & Support

| Item | Value |
|------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-04 |
| **Environment** | Azure Lab (DNvidiaBTANF) |
| **Status** | Ready for Production-like Testing |
| **Kubernetes** | v1.27+ (AKS standard) |
| **Bash** | v4.0+ (scripts use standard features) |

## References

- [Azure AKS Documentation](https://learn.microsoft.com/en-us/azure/aks/)
- [Kubernetes Official Docs](https://kubernetes.io/docs/)
- [Azure CLI Reference](https://learn.microsoft.com/en-us/cli/azure/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)

---

**Last Updated:** 2026-03-04
**Environment:** Azure Lab (DNvidiaBTANF)
**Ready for Deployment:** YES
