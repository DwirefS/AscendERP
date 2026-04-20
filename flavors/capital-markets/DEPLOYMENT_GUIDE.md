# Capital Markets Platform - Deployment Guide

## Overview

This deployment guide covers the ANTS Capital Markets multi-agent platform with Docker, PostgreSQL, and Redis for local development and production deployment to Azure (DNvidiaBTANF resource group).

## Project Structure

```
flavors/capital-markets/
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yaml        # Local development stack
├── api_gateway.py            # FastAPI entry point
├── DEPLOYMENT_GUIDE.md       # This file
│
├── agents/                   # Trading agents (TradingAgent, RiskManagementAgent, etc.)
├── workflows/                # LangGraph workflows (TradeLifecycleWorkflow, RiskAssessment, etc.)
├── models/                   # Data models (market data, risk, portfolio optimization)
├── data/                     # Data utilities (market_data_simulator, seed_data)
├── councils/                 # Multi-agent councils (TradingCouncil, RiskCommittee)
├── experts/                  # Expert agents (EquityAnalyst, DerivativesExpert, etc.)
├── config/                   # Configuration files
└── tests/                    # Test suite
```

## Prerequisites

- Docker & Docker Compose (v1.29+)
- Python 3.11+ (for local development)
- Git
- Azure CLI (for cloud deployment)

## Quick Start (Local Development)

### 1. Build and Start Services

```bash
cd flavors/capital-markets/

# Create .env file with configuration
cat > .env << 'EOF'
POSTGRES_USER=capital_markets
POSTGRES_PASSWORD=secure_password_change_me
POSTGRES_DB=capital_markets_db
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
AZURE_RESOURCE_GROUP=DNvidiaBTANF
ENV=development
LOG_LEVEL=INFO
EOF

# Start the stack
docker-compose up -d

# Verify services are healthy
docker-compose ps
```

### 2. Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs

# Check readiness
curl http://localhost:8000/ready

# Test database connection
docker-compose exec postgres psql -U capital_markets -d capital_markets_db -c "SELECT 1"

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### 3. View Logs

```bash
# Follow API logs
docker-compose logs -f capital-markets-api

# View database logs
docker-compose logs -f postgres

# View Redis logs
docker-compose logs -f redis
```

## API Endpoints

### Health & Status

- **GET /health** - Liveness probe (for Kubernetes/load balancers)
- **GET /ready** - Readiness probe (checks dependencies)
- **GET /** - Service information

### Trading Operations

- **POST /api/v1/trade** - Submit trade order
  ```bash
  curl -X POST http://localhost:8000/api/v1/trade \
    -H "Content-Type: application/json" \
    -d '{
      "client_id": "CLIENT-001",
      "ticker": "AAPL",
      "side": "buy",
      "quantity": 1000,
      "order_type": "market",
      "urgency": "normal"
    }'
  ```

### Risk Management

- **POST /api/v1/risk/assess** - Assess portfolio risk
  ```bash
  curl -X POST http://localhost:8000/api/v1/risk/assess \
    -H "Content-Type: application/json" \
    -d '{
      "portfolio_id": "PORTFOLIO-001",
      "include_scenarios": true,
      "time_horizon": "1d"
    }'
  ```

### Client Management

- **POST /api/v1/client/onboard** - Onboard new client
  ```bash
  curl -X POST http://localhost:8000/api/v1/client/onboard \
    -H "Content-Type: application/json" \
    -d '{
      "client_name": "Acme Capital",
      "client_type": "corporate",
      "jurisdiction": "US",
      "trading_profile": "moderate"
    }'
  ```

### Portfolio Management

- **GET /api/v1/portfolio/{portfolio_id}** - Get portfolio summary
  ```bash
  curl http://localhost:8000/api/v1/portfolio/PORTFOLIO-001
  ```

### Metrics & Monitoring

- **GET /api/v1/metrics** - Get system metrics and OVI
  ```bash
  curl http://localhost:8000/api/v1/metrics
  ```

## Database Setup

### Initialize Schema

The docker-compose file includes an init-db.sql mount point. Create this file:

```sql
-- flavors/capital-markets/init-db.sql
CREATE EXTENSION IF NOT EXISTS pgvector;

CREATE TABLE IF NOT EXISTS trades (
    trade_id UUID PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    execution_time TIMESTAMP,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id UUID PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL,
    total_value FLOAT,
    cash_balance FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id),
    ticker VARCHAR(10) NOT NULL,
    shares FLOAT NOT NULL,
    avg_cost FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Environment Variables

### Required

```bash
POSTGRES_USER=capital_markets
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=capital_markets_db
DATABASE_URL=postgresql://capital_markets:password@postgres:5432/capital_markets_db
REDIS_URL=redis://redis:6379/0
```

### Optional (Development)

```bash
ENV=development
LOG_LEVEL=INFO
ENABLE_TRACING=false
```

### Azure Integration

```bash
AZURE_SUBSCRIPTION_ID=your_subscription_id
AZURE_RESOURCE_GROUP=DNvidiaBTANF
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
```

### LLM Configuration

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.7
```

## Deployment to Azure

### 1. Prerequisites

```bash
# Login to Azure
az login

# Set active subscription
az account set --subscription <subscription-id>

# Create container registry (if not exists)
az acr create --resource-group DNvidiaBTANF \
  --name capitalmarketsregistry \
  --sku Basic
```

### 2. Build and Push Image

```bash
# Build Docker image
docker build -t capital-markets:latest .

# Tag for Azure Container Registry
docker tag capital-markets:latest \
  capitalmarketsregistry.azurecr.io/capital-markets:latest

# Login to ACR
az acr login --name capitalmarketsregistry

# Push image
docker push capitalmarketsregistry.azurecr.io/capital-markets:latest
```

### 3. Deploy to Azure Container Instances

```bash
az container create \
  --resource-group DNvidiaBTANF \
  --name capital-markets-api \
  --image capitalmarketsregistry.azurecr.io/capital-markets:latest \
  --registry-login-server capitalmarketsregistry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --ports 8000 \
  --environment-variables \
    ENV=production \
    DATABASE_URL="postgresql://..." \
    REDIS_URL="..." \
    AZURE_KEY_VAULT_URL="..." \
  --dns-name-label capital-markets \
  --cpu 2 \
  --memory 3.5
```

### 4. Deploy to Azure Kubernetes Service (AKS)

Create deployment manifests:

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: capital-markets-api
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: capital-markets
  template:
    metadata:
      labels:
        app: capital-markets
    spec:
      containers:
      - name: api
        image: capitalmarketsregistry.azurecr.io/capital-markets:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: capital-markets-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: capital-markets-secrets
              key: redis-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: capital-markets-service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: capital-markets
```

Deploy:

```bash
# Create secrets
kubectl create secret generic capital-markets-secrets \
  --from-literal=database-url='postgresql://...' \
  --from-literal=redis-url='redis://...'

# Deploy
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get pods -l app=capital-markets
kubectl logs -f deployment/capital-markets-api
```

## Testing

### Unit Tests

```bash
# Run with pytest
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

### Integration Tests

```bash
# Start services
docker-compose up -d

# Run integration tests
pytest tests/integration/ -v

# Cleanup
docker-compose down
```

### Load Testing

```bash
# Using locust
pip install locust

# Create locustfile.py and run
locust -f locustfile.py --host http://localhost:8000
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs capital-markets-api

# Common issues:
# 1. Port already in use: change port mapping
# 2. Database not ready: wait for postgres health check
# 3. Missing env vars: check .env file
```

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose exec postgres pg_isready

# Check connection string
echo $DATABASE_URL

# Connect directly
docker-compose exec postgres psql -U capital_markets -d capital_markets_db
```

### Redis Connection Issues

```bash
# Verify Redis is running
docker-compose exec redis redis-cli ping

# Check Redis memory
docker-compose exec redis redis-cli info memory
```

## Monitoring & Observability

### Enable Jaeger Tracing

Uncomment in docker-compose.yaml:

```yaml
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"  # UI
```

Access at: http://localhost:16686

### Enable Prometheus Metrics

Uncomment in docker-compose.yaml and configure endpoints.

### Logs

Logs are written to `./logs/` directory (mounted volume).

## Security Checklist

- [ ] Change all default passwords in .env
- [ ] Use Azure Key Vault for secrets
- [ ] Enable HTTPS in production (configure reverse proxy)
- [ ] Restrict CORS to trusted origins
- [ ] Enable authentication (JWT tokens)
- [ ] Setup network policies in Kubernetes
- [ ] Enable pod security policies
- [ ] Regular security scanning of images
- [ ] Implement rate limiting
- [ ] Enable audit logging

## Performance Tuning

### Database Connection Pooling

```bash
# In docker-compose.yaml environment:
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### Redis Caching

```bash
# Configure TTL
REDIS_CACHE_TTL=3600  # 1 hour
```

### API Workers

```bash
# In docker-compose.yaml:
WORKERS=4  # Adjust based on CPU cores
```

## Cleanup

```bash
# Stop services
docker-compose down

# Remove volumes (careful - data loss)
docker-compose down -v

# Remove images
docker rmi capital-markets:latest
```

## Support & Documentation

- API Docs: http://localhost:8000/docs
- Architecture: See AGENTS_ARCHITECTURE.md
- Agent Reference: See AGENT_REFERENCE.md
- README: See README.md

## Version History

- v1.0.0 (March 2024) - Initial release
  - Trade lifecycle workflow
  - Risk assessment
  - Client onboarding
  - Portfolio management
  - Multi-agent council system
