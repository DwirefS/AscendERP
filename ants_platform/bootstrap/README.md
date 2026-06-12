# antsctl - ANTS Control CLI

Command-line interface for deploying and managing the AI-Agent Native Tactical System (ANTS).

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install antsctl
pip install -e .

# Verify installation
antsctl --help
```

## Quick Start

```bash
# Validate a spec file
antsctl validate ants-spec.yaml

# Deploy ANTS (dry-run first)
antsctl deploy ants-spec.yaml --dry-run --environment dev

# Deploy to environment
antsctl deploy ants-spec.yaml --environment dev

# Check deployment status
antsctl status --environment dev

# View component logs
antsctl logs api-gateway --lines 100
antsctl logs orchestrator --follow
```

## Configuration

antsctl uses environment variables for configuration:

```bash
# Database connection
export ANTS_DB_CONNECTION="postgresql://user:pass@localhost:5432/ants"
export ANTS_DB_HOST="localhost"
export ANTS_DB_NAME="ants"
export ANTS_DB_USER="ants_user"

# API Gateway
export ANTS_API_GATEWAY="https://api.ants.example.com"
export ANTS_API_KEY="your-api-key"

# Kubernetes context
export KUBECONFIG=~/.kube/config
```

## Commands

### Deployment

#### `deploy`
Deploy ANTS from specification file.

```bash
antsctl deploy <spec_file> [OPTIONS]

Options:
  --dry-run           Show what would be deployed
  --environment, -e   Target environment (dev/staging/production)

Examples:
  antsctl deploy ants-spec.yaml --dry-run
  antsctl deploy ants-spec.yaml -e production
```

#### `validate`
Validate ANTS specification file.

```bash
antsctl validate <spec_file>

Example:
  antsctl validate ants-spec.yaml
```

#### `status`
Show ANTS deployment status.

```bash
antsctl status [OPTIONS]

Options:
  --environment, -e   Target environment

Example:
  antsctl status -e dev
```

#### `scale`
Scale agent workers.

```bash
antsctl scale <agent_type> --replicas <count> [OPTIONS]

Options:
  --replicas, -r      Number of replicas
  --environment, -e   Target environment

Example:
  antsctl scale finance.reconciliation --replicas 5 -e production
```

#### `logs`
View component logs.

```bash
antsctl logs <component> [OPTIONS]

Options:
  --follow, -f        Follow log output
  --lines, -n         Number of lines to show

Examples:
  antsctl logs api-gateway -n 500
  antsctl logs orchestrator --follow
```

### Agent Management

#### `agent list`
List registered agents.

```bash
antsctl agent list [OPTIONS]

Options:
  --environment, -e   Target environment

Example:
  antsctl agent list -e dev
```

#### `agent invoke`
Invoke an agent.

```bash
antsctl agent invoke <agent_type> [OPTIONS]

Options:
  --input, -i         Input JSON file
  --tenant, -t        Tenant ID (required)

Example:
  antsctl agent invoke finance.reconciliation \
    --input input.json \
    --tenant acme-corp
```

### Memory Management

#### `memory search`
Search agent memory.

```bash
antsctl memory search <query> [OPTIONS]

Options:
  --type, -t          Memory type (semantic/episodic/procedural)
  --tenant            Tenant ID (required)
  --limit, -n         Result limit

Example:
  antsctl memory search "revenue recognition" \
    --type semantic \
    --tenant acme-corp \
    --limit 10
```

### Metrics

#### `metrics clear`
Show CLEAR metrics.

```bash
antsctl metrics clear [OPTIONS]

Options:
  --environment, -e   Target environment

Example:
  antsctl metrics clear -e production
```

Displays:
- **Cost**: Token usage and estimated USD cost
- **Latency**: P50, P95, P99 response times
- **Efficacy**: Success rate and confidence
- **Assurance**: Policy compliance and audit coverage
- **Reliability**: Uptime and error rate

### Policy Management

#### `policy test`
Run OPA policy tests.

```bash
antsctl policy test

Example:
  antsctl policy test
```

#### `policy validate`
Validate a policy file.

```bash
antsctl policy validate <policy_file>

Example:
  antsctl policy validate platform/policies/ants/financial_controls.rego
```

#### `policy evaluate`
Evaluate a policy with input data.

```bash
antsctl policy evaluate <policy_path> --input <input_file>

Example:
  antsctl policy evaluate \
    platform/policies/ants/financial_controls.rego \
    --input test_transaction.json
```

### Backup & Restore

#### `backup`
Backup ANTS data and configuration.

```bash
antsctl backup --output <directory> [OPTIONS]

Options:
  --output, -o        Backup output directory (required)
  --environment, -e   Target environment

Example:
  antsctl backup --output /backups/ants -e production
```

Backs up:
- PostgreSQL database (full dump)
- Kubernetes resources (deployments, services, configmaps, secrets)
- Configuration files and templates

#### `restore`
Restore ANTS from backup.

```bash
antsctl restore <backup_dir> [OPTIONS]

Options:
  --environment, -e   Target environment
  --confirm           Confirm restore operation (required)

Example:
  antsctl restore /backups/ants/ants-backup-20250122-143000 \
    --environment production \
    --confirm
```

**Warning**: Restore replaces existing data. Always use `--confirm` flag.

## Specification File Format

```yaml
version: "1.0"

tenant:
  name: "Acme Corporation"
  id: "acme-corp"

regions:
  - "eastus"
  - "westus2"

infrastructure:
  anf:
    capacity_tb: 10
    service_levels:
      - ultra
      - premium
      - standard

  aks:
    node_count: 5
    vm_size: "Standard_D8s_v3"
    gpu_enabled: true

  databricks:
    sku: "premium"
    autoscale: true

  ai_foundry:
    enabled: true
    models:
      - "gpt-4o"
      - "gpt-4o-mini"

agents:
  - type: "finance.reconciliation"
    replicas: 3
    tier: "high_priority"

  - type: "cybersecurity.defender_triage"
    replicas: 5
    tier: "critical"

  - type: "retail.inventory"
    replicas: 2
    tier: "standard"

policies:
  financial_controls: true
  data_governance: true
  security_policies: true
  agent_lifecycle: true

observability:
  prometheus: true
  grafana: true
  jaeger: true
  log_analytics: true
```

## Common Workflows

### Initial Deployment

```bash
# 1. Validate spec
antsctl validate ants-spec.yaml

# 2. Dry-run deployment
antsctl deploy ants-spec.yaml --dry-run -e dev

# 3. Deploy to dev
antsctl deploy ants-spec.yaml -e dev

# 4. Check status
antsctl status -e dev

# 5. View logs
antsctl logs api-gateway -n 100
```

### Scaling Agents

```bash
# List current agents
antsctl agent list -e production

# Scale up finance agents
antsctl scale finance.reconciliation --replicas 10 -e production

# Verify scaling
antsctl status -e production
```

### Monitoring

```bash
# Check CLEAR metrics
antsctl metrics clear -e production

# Stream logs
antsctl logs orchestrator --follow

# Search agent memory
antsctl memory search "fraud detection" \
  --type semantic \
  --tenant acme-corp \
  --limit 20
```

### Policy Testing

```bash
# Run all policy tests
antsctl policy test

# Validate specific policy
antsctl policy validate platform/policies/ants/security_policies.rego

# Test policy decision
echo '{"agent_type": "finance.reconciliation", "amount": 50000}' > input.json
antsctl policy evaluate \
  platform/policies/ants/financial_controls.rego \
  --input input.json
```

### Backup & Recovery

```bash
# Create backup
antsctl backup --output /backups/ants -e production

# List backups
ls -lh /backups/ants/

# Restore from backup
antsctl restore /backups/ants/ants-backup-20250122-143000 \
  --environment staging \
  --confirm
```

## Troubleshooting

### Connection Issues

```bash
# Check Kubernetes connection
kubectl cluster-info

# Check database connection
psql $ANTS_DB_CONNECTION -c "SELECT 1;"

# Verify API gateway
curl $ANTS_API_GATEWAY/health
```

### Deployment Failures

```bash
# Check Terraform state
cd infra/terraform/envs/dev
terraform show

# Check Helm releases
helm list -n ants

# View pod status
kubectl get pods -n ants

# Check pod logs
kubectl logs -n ants <pod-name>
```

### Agent Issues

```bash
# List agents
antsctl agent list

# Check agent logs
antsctl logs agent-finance-reconciliation

# Restart agent deployment
kubectl rollout restart deployment/agent-finance-reconciliation -n ants
```

## Environment-Specific Operations

### Development

```bash
# Use dev environment
antsctl deploy ants-spec.yaml -e dev
antsctl status -e dev

# Local database
export ANTS_DB_CONNECTION="postgresql://localhost:5432/ants_dev"
```

### Staging

```bash
# Deploy to staging
antsctl deploy ants-spec.yaml -e staging

# Test before production
antsctl agent invoke finance.reconciliation \
  --input test_input.json \
  --tenant test-tenant
```

### Production

```bash
# Always dry-run first
antsctl deploy ants-spec.yaml --dry-run -e production

# Backup before deployment
antsctl backup --output /backups/pre-deploy -e production

# Deploy with monitoring
antsctl deploy ants-spec.yaml -e production

# Watch deployment
watch -n 5 'antsctl status -e production'

# Monitor metrics
antsctl metrics clear -e production
```

## Advanced Usage

### Custom Terraform Variables

```bash
# Override default terraform directory
TERRAFORM_DIR=/custom/path antsctl deploy ants-spec.yaml
```

### Custom Helm Values

Create `custom-values.yaml`:

```yaml
apiGateway:
  replicas: 5
  resources:
    requests:
      memory: "4Gi"
      cpu: "2000m"
```

Then reference in spec file or pass via environment.

### Multi-Region Deployment

```yaml
regions:
  - "eastus"
  - "westus2"
  - "westeurope"

replication:
  anf:
    cross_region: true
  database:
    geo_replicated: true
```

## Security Best Practices

1. **API Keys**: Store in secure vault, rotate regularly
2. **Database Credentials**: Use managed identities when possible
3. **Backups**: Encrypt backups, test restore procedures
4. **Policies**: Test policies before deploying
5. **RBAC**: Use least-privilege access

## Support

- Documentation: `/docs/`
- Issues: GitHub Issues
- Slack: #ants-support

## License

Proprietary - Acme Corporation
