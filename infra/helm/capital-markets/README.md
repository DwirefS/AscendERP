# Capital Markets ANTS Helm Chart

Kubernetes Helm chart for deploying the Capital Markets flavor of the ANTS (AI-Agent Native Tactical System) platform.

## Overview

This Helm chart deploys:
- 6 specialized capital markets agents (Trading, Risk, Derivatives, Portfolio, Compliance, Client Service)
- PostgreSQL database for state and transaction persistence
- Azure NetApp Files (NFS) mounts for agent memory (episodic, semantic, procedural)
- ConfigMaps for agent, council, and model configuration
- Services for inter-agent communication

## Quick Start

### Prerequisites

- Kubernetes >= 1.24
- Helm >= 3.0
- Azure subscription (for Key Vault and ANF)
- kubectl configured to access your cluster

### Installation

```bash
# Add Bitnami Helm repository (for PostgreSQL dependency)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Navigate to chart directory
cd infra/helm/capital-markets

# Update dependencies
helm dependency update

# Install the chart (lab environment)
helm install capital-markets . \
  -f ../../values-lab.yaml \
  --namespace default \
  --create-namespace

# Or for production
helm install capital-markets . \
  -f ../../values-prod.yaml \
  --namespace capital-markets \
  --create-namespace
```

### Verify Installation

```bash
# Check Helm release status
helm status capital-markets

# Get pod status
kubectl get pods -l flavor=capital-markets

# View logs from an agent
kubectl logs -f deployment/trading-agent

# Port-forward to test an agent
kubectl port-forward svc/trading-agent 8000:8000
```

## Values Configuration

### Global Settings

```yaml
global:
  environment: "lab"           # lab, dev, staging, production
  imageRegistry: "your-registry.azurecr.io"
  namespace: "default"
  timezone: "UTC"
```

### Agent Configuration

Each agent can be configured independently:

```yaml
agents:
  trading:
    enabled: true
    replicaCount: 1
    resources:
      requests:
        cpu: "100m"
        memory: "256Mi"
      limits:
        cpu: "200m"
        memory: "512Mi"
```

### Storage Configuration

Azure NetApp Files mounts for agent memory:

```yaml
storage:
  anf:
    enabled: true
    mounts:
      models:
        path: "/mnt/anf/models"
        nfsServer: "nfs-server-ip"
        nfsPath: "/models"
```

### Database Configuration

PostgreSQL settings:

```yaml
postgresql:
  enabled: true
  auth:
    username: "ants"
    password: "CHANGE_ME"
    database: "capital_markets"
  primary:
    persistence:
      size: "10Gi"
```

## Configuration Management

### YAML Configuration Files

The chart uses three ConfigMaps to manage agent configurations:

1. **agents_config.yaml** - Agent models, tools, memory settings
2. **councils_config.yaml** - Council voting rules and authority limits
3. **models_config.yaml** - Risk parameters, trading limits, simulation settings

These files are mounted into agent containers at:
- `/etc/config/agents_config.yaml`
- `/etc/config/councils_config.yaml`
- `/etc/config/models_config.yaml`

### Updating Configuration

To update agent configuration without redeploying:

```bash
# Update ConfigMap
kubectl create configmap capital-markets-agents-config \
  --from-file=agents_config.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up changes
kubectl rollout restart deployment/trading-agent
```

## Storage Architecture

### Agent Memory Tiers

| Tier | Type | Purpose | ANF Level |
|---|---|---|---|
| Models | Cache | Cached LLM weights | Ultra |
| Episodic | Recent | Last 30 days transactions | Premium |
| Semantic | Reference | Market concepts, rules | Premium |
| Procedural | Learned | Execution patterns | Premium |
| Lakehouse | Archive | Analytics, cold storage | Standard |

### NFS Mount Points

All NFS mounts are configured in `values.yaml`:

```yaml
storage:
  anf:
    mounts:
      episodic:
        path: "/mnt/anf/memory/episodic"
        nfsServer: "10.0.2.4"
        nfsPath: "/episodic"
```

## Inter-Agent Communication

Agents communicate via Kubernetes Services:

```
Trading Agent          (port 8000)
Risk Agent             (port 8001)
Derivatives Agent      (port 8002)
Portfolio Manager      (port 8003)
Compliance Agent       (port 8004)
Client Service Agent   (port 8005)
```

Services use `<agent-name>-agent.<namespace>.svc.cluster.local` for DNS discovery.

## Security

### RBAC Configuration

The chart creates:
- ServiceAccount: `capital-markets-agents`
- ClusterRole: Permissions for ConfigMap/Secret/Pod access
- Role: Namespace-specific permissions

### Azure Key Vault Integration

Secrets are stored in Azure Key Vault and mounted via workload identity:

```bash
# Configure workload identity
az aks workload-identity miic create \
  --cluster-name my-cluster \
  --namespace default \
  --name capital-markets-agents
```

### Network Policies

Network policies (optional) can restrict traffic between agents:

```yaml
networkPolicy:
  enabled: true  # Requires Calico or other CNI
```

## Monitoring and Observability

### Prometheus Metrics

Each agent exposes metrics on port 9090:

```
http://<agent-name>-agent:9090/metrics
```

### Grafana Dashboards

Pre-built dashboards available for:
- Agent overview and status
- Council decision metrics
- Risk and exposure metrics
- Trade execution metrics

### Logs

View agent logs:

```bash
# Real-time logs
kubectl logs -f deployment/trading-agent

# Historical logs
kubectl logs deployment/trading-agent --tail=100

# All agents
kubectl logs -f -l component=agent --all-containers=true
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name>

# Check logs for errors
kubectl logs <pod-name>

# Check resource availability
kubectl top nodes
kubectl top pods
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
kubectl exec -it <pod-name> -- psql \
  -h postgresql.default.svc.cluster.local \
  -U ants \
  -d capital_markets \
  -c "SELECT version();"
```

### ANF Mount Failures

```bash
# Check mount status inside pod
kubectl exec -it <pod-name> -- df -h /mnt/anf/

# Test NFS connectivity
kubectl exec -it <pod-name> -- nslookup nfs-server
```

### Configuration Issues

```bash
# View loaded ConfigMap
kubectl get configmap capital-markets-agents-config -o yaml

# Check agent environment variables
kubectl exec -it <pod-name> -- env | grep -i config
```

## Upgrading the Chart

```bash
# Update values
helm values capital-markets > values-current.yaml
# Edit values-current.yaml as needed

# Upgrade release
helm upgrade capital-markets . \
  -f values-current.yaml \
  --namespace default

# View release history
helm history capital-markets

# Rollback if needed
helm rollback capital-markets 1
```

## Environment-Specific Values

### Lab Environment

File: `values-lab.yaml`
- 1 replica per agent
- Minimal resources (100m CPU, 256Mi memory)
- PostgreSQL: burstable tier, 5GB
- No monitoring or high availability

### Production Environment

File: `values-prod.yaml` (create as needed)
- 3+ replicas per agent
- Higher resource limits (500m CPU, 1Gi memory)
- PostgreSQL: HA with replicas, 100GB+
- Full monitoring, alerts, network policies
- Pod disruption budgets

## Kubernetes Features Used

- Deployments: Agent pods with rolling updates
- Services: ClusterIP for inter-pod communication
- ConfigMaps: Externalized configuration
- Secrets: Sensitive data (mounted from Key Vault)
- Probes: Liveness and readiness checks
- RBAC: ServiceAccounts and ClusterRoles
- SecurityContext: Non-root user, dropped capabilities

## Performance Tuning

### Resource Limits

Adjust per-agent resources based on workload:

```yaml
agents:
  trading:
    resources:
      requests:
        cpu: "250m"      # Increase for high-throughput
        memory: "512Mi"  # Increase for larger models
      limits:
        cpu: "1000m"
        memory: "2Gi"
```

### Pod Affinity

Configure pod anti-affinity to spread agents across nodes:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: "app"
                operator: "In"
                values: ["trading-agent"]
          topologyKey: "kubernetes.io/hostname"
```

### Autoscaling

Enable Horizontal Pod Autoscaler (HPA):

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

## Support and Contributing

For issues, feature requests, or contributions:
- GitHub: https://github.com/your-org/ants
- Email: ants-team@your-org.com

## License

Apache License 2.0 - See LICENSE file for details

## See Also

- [Capital Markets Architecture](../../flavors/capital-markets/AGENTS_ARCHITECTURE.md)
- [Terraform Infrastructure](../terraform/envs/lab/)
- [Configuration YAML Files](../../flavors/capital-markets/config/)
- [Deployment Guide](../../lab-lessons/deployment-notes.md)
