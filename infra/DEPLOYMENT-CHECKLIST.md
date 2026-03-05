# ANTS Capital Markets - Deployment Checklist

Use this checklist to ensure proper deployment and configuration.

## Pre-Deployment Checklist

### Environment Setup

- [ ] Azure CLI installed: `az --version`
- [ ] kubectl installed: `kubectl version --client`
- [ ] Docker installed: `docker --version`
- [ ] Helm installed: `helm version --short`
- [ ] At least 20 GB free disk space
- [ ] Internet connectivity confirmed

### Azure Account

- [ ] Logged into Azure: `az login`
- [ ] Correct subscription selected: `az account show`
- [ ] Access to resource group `DNvidiaBTANF` verified
- [ ] Have contributor or owner role in the resource group
- [ ] Budget alerts configured in Azure (optional)

### Code & Configuration

- [ ] Working directory: `/path/to/AscendERP`
- [ ] `infra/deploy-lab.sh` exists and is executable
- [ ] `infra/teardown-lab.sh` exists and is executable
- [ ] `infra/k8s/capital-markets/` directory with all 7 YAML files
- [ ] `infra/README-DEPLOYMENT.md` exists

### Secrets & Configuration

- [ ] Reviewed `infra/k8s/capital-markets/secrets.yaml`
- [ ] Updated placeholder values or plan to set post-deploy:
  - [ ] `DATABASE_URL`
  - [ ] `OPENAI_API_KEY`
  - [ ] `AZURE_KEY_VAULT_URI` (if using Key Vault)
  - [ ] `JWT_SECRET`
  - [ ] `RABBITMQ_URL`
- [ ] ConfigMap defaults acceptable (or noted for updates)

### Docker Image

- [ ] Dockerfile exists in project root
- [ ] Dockerfile builds successfully: `docker build -t test .`
- [ ] Image size is reasonable (< 1GB)
- [ ] All dependencies are listed

## Deployment Checklist

### Pre-Deployment Validation

```bash
# Run dry-run to validate everything
./infra/deploy-lab.sh --dry-run
```

- [ ] Script runs without errors
- [ ] All prerequisites are satisfied
- [ ] Correct resource group detected
- [ ] Cost estimate reviewed and acceptable
- [ ] No existing resources will be overwritten (check output)

### Execute Deployment

```bash
# Run actual deployment
./infra/deploy-lab.sh
```

During deployment, confirm:
- [ ] AKS cluster creation (if needed) - you WILL be prompted
- [ ] ACR creation (if needed) - you WILL be prompted
- [ ] Cost warnings acknowledged
- [ ] Proceed with deployment - you WILL be prompted

Expected timeline:
- [ ] Prerequisites check: < 1 minute
- [ ] AKS creation (if new): 10-15 minutes
- [ ] ACR creation (if new): 1-2 minutes
- [ ] Image build/push: 5-10 minutes
- [ ] Manifest application: 1-2 minutes
- [ ] Rollout verification: 2-5 minutes
- **Total expected time: 20-35 minutes**

### Post-Deployment Verification

After script completes successfully:

```bash
# 1. Check namespace
kubectl get ns ants-capital-markets
```
- [ ] Namespace exists

```bash
# 2. Check ConfigMap
kubectl get configmap -n ants-capital-markets
kubectl describe configmap ants-cm-config -n ants-capital-markets
```
- [ ] `ants-cm-config` exists
- [ ] All configuration keys present

```bash
# 3. Check Secrets
kubectl get secret -n ants-capital-markets
```
- [ ] `ants-cm-secrets` exists

```bash
# 4. Check Deployment
kubectl get deployment -n ants-capital-markets
kubectl describe deployment capital-markets-api -n ants-capital-markets
```
- [ ] Deployment exists
- [ ] Correct image: `antslab.azurecr.io/ants-capital-markets:latest`
- [ ] 1 replica running (or desired count)
- [ ] Resource limits correct: CPU 500m, memory 1Gi
- [ ] Resource requests correct: CPU 250m, memory 512Mi

```bash
# 5. Check Pods
kubectl get pods -n ants-capital-markets
kubectl get pod <pod-name> -n ants-capital-markets -o wide
```
- [ ] Pod is in `Running` status
- [ ] Pod IP is assigned
- [ ] Container is ready (Ready 1/1)
- [ ] 0 restarts

```bash
# 6. Check Service
kubectl get svc -n ants-capital-markets
kubectl describe svc capital-markets-api -n ants-capital-markets
```
- [ ] Service exists (ClusterIP)
- [ ] Port 8000 is mapped correctly
- [ ] Endpoints show pod IP

```bash
# 7. Check HPA
kubectl get hpa -n ants-capital-markets
kubectl describe hpa capital-markets-api-hpa -n ants-capital-markets
```
- [ ] HPA exists
- [ ] Min replicas: 1, Max replicas: 3
- [ ] CPU target: 70%
- [ ] Currently shows: 1 replica, < 100% CPU

```bash
# 8. Check Ingress
kubectl get ingress -n ants-capital-markets
kubectl describe ingress ants-cm-ingress -n ants-capital-markets
```
- [ ] Ingress exists
- [ ] Path mapping correct: `/api/v1/*`
- [ ] Ingress IP/hostname assigned (or pending)

```bash
# 9. Test health endpoints
kubectl port-forward -n ants-capital-markets svc/capital-markets-api 8000:8000 &

curl -v http://localhost:8000/health
curl -v http://localhost:8000/ready

kill %1  # Stop port-forward
```
- [ ] `/health` returns 200 OK
- [ ] `/ready` returns 200 OK
- [ ] Response time < 500ms

```bash
# 10. Check logs
kubectl logs -n ants-capital-markets -l app=ants,component=capital-markets-api
```
- [ ] No error messages
- [ ] Application started successfully
- [ ] No connection errors to dependencies
- [ ] Configuration loaded correctly

### Azure Resource Verification

```bash
# Check AKS cluster
az aks show -g DNvidiaBTANF -n ants-cm-lab-aks

# Verify tags
az aks show -g DNvidiaBTANF -n ants-cm-lab-aks --query "tags"
```
- [ ] Cluster exists
- [ ] All expected tags present: `project=ants-capital-markets`
- [ ] Node count correct: 2 nodes
- [ ] Node SKU correct: Standard_B2ms

```bash
# Check ACR
az acr show -g DNvidiaBTANF -n antslab

# List repositories
az acr repository list --name antslab

# Show tags
az acr repository show-tags --name antslab --repository ants-capital-markets
```
- [ ] ACR exists
- [ ] SKU is Basic
- [ ] Repository `ants-capital-markets` exists
- [ ] `latest` tag exists
- [ ] Other expected tags present

```bash
# Verify ACR-to-AKS attachment
az role assignment list --scope /subscriptions/<sub-id>/resourceGroups/DNvidiaBTANF/providers/Microsoft.ContainerRegistry/registries/antslab --query "[].principalId"
```
- [ ] AKS service principal has acrpull role

## Configuration & Secrets Setup

### Update Secrets

Choose one of these methods:

**Method 1: Edit YAML before deploying (easy, not recommended for prod)**
```bash
vim infra/k8s/capital-markets/secrets.yaml
# Replace all PLACEHOLDER values
# Then run: kubectl apply -f ...
```

**Method 2: Update after deployment (recommended)**
```bash
# Get existing secret
kubectl get secret ants-cm-secrets -n ants-capital-markets -o yaml > /tmp/secret.yaml

# Edit
nano /tmp/secret.yaml

# Apply
kubectl apply -f /tmp/secret.yaml
```

**Method 3: Use kubectl set env**
```bash
kubectl set env deployment/capital-markets-api \
  DATABASE_URL="postgresql://user:pass@host/db" \
  OPENAI_API_KEY="sk-..." \
  -n ants-capital-markets
```

Configure the following secrets:
- [ ] `DATABASE_URL`: Database connection string
- [ ] `OPENAI_API_KEY`: OpenAI API key
- [ ] `AZURE_KEY_VAULT_URI`: Key Vault endpoint (if used)
- [ ] `JWT_SECRET`: JWT signing secret (min 32 chars)
- [ ] `RABBITMQ_URL`: Message queue connection

### Update ConfigMap

```bash
# Edit ConfigMap
kubectl edit configmap ants-cm-config -n ants-capital-markets

# Or re-apply with changes
vim infra/k8s/capital-markets/configmap.yaml
kubectl apply -f infra/k8s/capital-markets/configmap.yaml
```

- [ ] `LOG_LEVEL`: Set appropriate level (INFO, DEBUG, WARN, ERROR)
- [ ] `ENVIRONMENT`: Verify set to "lab"
- [ ] `FLAVOR`: Verify set to "capital-markets"
- [ ] Agent configurations: Review and customize
- [ ] Council configurations: Review and customize
- [ ] Model configurations: Update with correct endpoints

## Monitoring & Health Checks

### Ongoing Monitoring

```bash
# Watch pods
kubectl get pods -n ants-capital-markets --watch

# View metrics (requires metrics-server)
kubectl top nodes
kubectl top pods -n ants-capital-markets

# Follow logs
kubectl logs -n ants-capital-markets -l app=ants -f
```

- [ ] Pod is stable (no crashes/restarts)
- [ ] CPU/memory usage acceptable
- [ ] No error messages in logs

### Set Up Alerts (Optional)

```bash
# Azure Monitor integration
az aks show -g DNvidiaBTANF -n ants-cm-lab-aks --query "addonProfiles"

# Check if Container Insights enabled
```

- [ ] Container Insights enabled (optional)
- [ ] Alert rules configured for pod failures
- [ ] Alert rules configured for high resource usage

## Cost Verification

### Review Azure Bills

```bash
# Check estimated cost
az billing subscription list-invoices -s <subscription-id>

# Monitor resource group spending
# Use Azure Portal: Resource Groups > DNvidiaBTANF > Cost Analysis
```

- [ ] Monthly estimated cost aligns with projection ($150-200)
- [ ] No unexpected resource creation
- [ ] Budget alerts haven't fired

## Cleanup & Teardown

### When Ready to Destroy

```bash
# List resources to be deleted
./infra/teardown-lab.sh

# Perform teardown
./infra/teardown-lab.sh --force
```

- [ ] Confirmed no other projects in resource group will be affected
- [ ] Confirmed RG itself won't be deleted
- [ ] Confirmed all data backed up if needed
- [ ] Acknowledged deletion cannot be easily undone

### Verify Cleanup

```bash
# Check namespace is deleted
kubectl get ns ants-capital-markets
# Should return: Error from server (NotFound)

# Verify Azure resources deleted
az aks list -g DNvidiaBTANF --query "[?tags.project=='ants-capital-markets']"
az acr list -g DNvidiaBTANF --query "[?tags.project=='ants-capital-markets']"
# Both should return empty list: []
```

- [ ] Namespace removed
- [ ] AKS cluster removed (may take 10-15 min)
- [ ] ACR removed
- [ ] No resources tagged with `project=ants-capital-markets`
- [ ] Other RG resources unaffected

## Troubleshooting Checklist

If something goes wrong:

### Deployment Failed

- [ ] Read full error message carefully
- [ ] Check prerequisites: `./infra/deploy-lab.sh --dry-run`
- [ ] Verify Azure login: `az account show`
- [ ] Check available quota in resource group
- [ ] Review Azure activity log for errors
- [ ] Retry from scratch if persistent: `./infra/teardown-lab.sh --force && ./infra/deploy-lab.sh`

### Pods Not Running

- [ ] Check pod status: `kubectl describe pod <name> -n ants-capital-markets`
- [ ] Check events for error messages
- [ ] Verify image exists: `az acr repository show-tags --name antslab --repository ants-capital-markets`
- [ ] Check image pull policy: Should be `IfNotPresent`
- [ ] Verify ACR-AKS attachment

### Connectivity Issues

- [ ] Verify service exists: `kubectl get svc -n ants-capital-markets`
- [ ] Check service endpoints: `kubectl describe svc capital-markets-api -n ants-capital-markets`
- [ ] Try port-forward: `kubectl port-forward svc/capital-markets-api 8000:8000 -n ants-capital-markets`
- [ ] Test locally: `curl http://localhost:8000/health`

### Configuration Issues

- [ ] Verify ConfigMap applied: `kubectl describe configmap ants-cm-config -n ants-capital-markets`
- [ ] Check for typos in keys
- [ ] Verify pod restarted after ConfigMap changes
- [ ] Check pod logs for configuration errors

### Resource Issues

- [ ] Check node resources: `kubectl top nodes`
- [ ] Check pod resource requests: `kubectl describe deployment capital-markets-api -n ants-capital-markets`
- [ ] Scale down if needed: `kubectl scale deployment capital-markets-api --replicas=1 -n ants-capital-markets`
- [ ] Consider increasing node count: `az aks scale -g DNvidiaBTANF -n ants-cm-lab-aks --node-count 3`

## Sign-Off Checklist

After completing all checks, sign off here:

- [ ] All prerequisites verified
- [ ] Deployment completed successfully
- [ ] All resources verified in Kubernetes
- [ ] All resources verified in Azure
- [ ] Health endpoints responding
- [ ] No errors in logs
- [ ] Monitoring configured
- [ ] Secrets properly configured
- [ ] Cost reviewed and acceptable
- [ ] Documentation updated
- [ ] Team notified of deployment

**Deployment Date:** ___________________
**Deployed By:** ___________________
**Verification Date:** ___________________
**Verified By:** ___________________

---

**Notes:**
(Add any special notes or deviations from standard deployment)

