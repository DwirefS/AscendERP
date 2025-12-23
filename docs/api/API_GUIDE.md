## ANTS Agent Management API Guide

Complete guide to using the ANTS API with code examples in Python, JavaScript, cURL, and C#.

## Table of Contents

1. [Authentication](#authentication)
2. [Quick Start](#quick-start)
3. [Agent Management](#agent-management)
4. [Task Execution](#task-execution)
5. [Memory Operations](#memory-operations)
6. [Policy Management](#policy-management)
7. [Monitoring](#monitoring)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)

## Authentication

All API requests require authentication using Azure AD Bearer tokens.

### Python

```python
from azure.identity import DefaultAzureCredential
import requests

# Get Azure AD token
credential = DefaultAzureCredential()
token = credential.get_token("https://api.ants.ai/.default")

# Configure headers
headers = {
    "Authorization": f"Bearer {token.token}",
    "Content-Type": "application/json"
}

# Make API request
response = requests.get(
    "https://api.ants.ai/v1/agents",
    headers=headers
)
```

### JavaScript/TypeScript

```javascript
const { DefaultAzureCredential } = require("@azure/identity");
const axios = require("axios");

// Get Azure AD token
const credential = new DefaultAzureCredential();
const token = await credential.getToken("https://api.ants.ai/.default");

// Make API request
const response = await axios.get("https://api.ants.ai/v1/agents", {
  headers: {
    "Authorization": `Bearer ${token.token}`,
    "Content-Type": "application/json"
  }
});
```

### cURL

```bash
# Get token using Azure CLI
TOKEN=$(az account get-access-token --resource https://api.ants.ai --query accessToken -o tsv)

# Make API request
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     https://api.ants.ai/v1/agents
```

## Quick Start

### Create an Agent

**Python**:
```python
import requests

def create_agent(name, agent_type, specialization, token):
    """Create a new agent."""
    url = "https://api.ants.ai/v1/agents"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": name,
        "type": agent_type,
        "specialization": specialization,
        "config": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage
agent = create_agent(
    name="Finance Reconciliation Agent",
    agent_type="finance",
    specialization="accounts_payable_reconciliation",
    token=your_token
)

print(f"Created agent: {agent['agent_id']}")
```

**JavaScript**:
```javascript
async function createAgent(name, agentType, specialization, token) {
  const response = await axios.post(
    "https://api.ants.ai/v1/agents",
    {
      name: name,
      type: agentType,
      specialization: specialization,
      config: {
        model: "gpt-4",
        temperature: 0.7,
        max_tokens: 2000
      }
    },
    {
      headers: { "Authorization": `Bearer ${token}` }
    }
  );

  return response.data;
}

// Example usage
const agent = await createAgent(
  "Finance Reconciliation Agent",
  "finance",
  "accounts_payable_reconciliation",
  yourToken
);

console.log(`Created agent: ${agent.agent_id}`);
```

**cURL**:
```bash
curl -X POST https://api.ants.ai/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Finance Reconciliation Agent",
    "type": "finance",
    "specialization": "accounts_payable_reconciliation",
    "config": {
      "model": "gpt-4",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'
```

### Execute a Task

**Python**:
```python
def execute_task(agent_id, task_description, token):
    """Execute a task with an agent."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}/execute"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "task_description": task_description,
        "priority": "normal",
        "context": {
            "department": "finance",
            "quarter": "Q4_2024"
        }
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage
execution = execute_task(
    agent_id="finance-reconciliation-001",
    task_description="Reconcile accounts payable for Q4 2024",
    token=your_token
)

print(f"Execution ID: {execution['execution_id']}")
print(f"Status: {execution['status']}")
```

**JavaScript**:
```javascript
async function executeTask(agentId, taskDescription, token) {
  const response = await axios.post(
    `https://api.ants.ai/v1/agents/${agentId}/execute`,
    {
      task_description: taskDescription,
      priority: "normal",
      context: {
        department: "finance",
        quarter: "Q4_2024"
      }
    },
    {
      headers: { "Authorization": `Bearer ${token}` }
    }
  );

  return response.data;
}

// Example usage
const execution = await executeTask(
  "finance-reconciliation-001",
  "Reconcile accounts payable for Q4 2024",
  yourToken
);

console.log(`Execution ID: ${execution.execution_id}`);
console.log(`Status: ${execution.status}`);
```

### Poll for Execution Result

**Python**:
```python
import time

def wait_for_execution(execution_id, token, timeout=300, poll_interval=5):
    """Wait for task execution to complete."""
    url = f"https://api.ants.ai/v1/executions/{execution_id}"
    headers = {"Authorization": f"Bearer {token}"}

    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        execution = response.json()
        status = execution["status"]

        if status == "completed":
            return execution
        elif status == "failed":
            raise Exception(f"Execution failed: {execution.get('error')}")

        time.sleep(poll_interval)

    raise TimeoutError("Execution timeout")

# Example usage
result = wait_for_execution(execution["execution_id"], your_token)
print(f"Result: {result['result']}")
print(f"Duration: {result['metrics']['duration_seconds']}s")
print(f"Cost: ${result['metrics']['cost_usd']}")
```

## Agent Management

### List Agents

**Python**:
```python
def list_agents(token, status=None, page=1, page_size=20):
    """List all agents with optional filtering."""
    url = "https://api.ants.ai/v1/agents"
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "page": page,
        "page_size": page_size
    }

    if status:
        params["status"] = status

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()

# Example usage
agents = list_agents(your_token, status="active")
for agent in agents["agents"]:
    print(f"{agent['agent_id']}: {agent['name']} ({agent['status']})")

# Pagination info
pagination = agents["pagination"]
print(f"Page {pagination['page']} of {pagination['total_pages']}")
print(f"Total agents: {pagination['total_items']}")
```

### Get Agent Details

**Python**:
```python
def get_agent(agent_id, token):
    """Get detailed agent information."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage
agent = get_agent("finance-reconciliation-001", your_token)
print(f"Name: {agent['name']}")
print(f"Type: {agent['type']}")
print(f"Status: {agent['status']}")
print(f"Config: {agent['config']}")
```

### Update Agent

**Python**:
```python
def update_agent(agent_id, token, **updates):
    """Update agent configuration."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.put(url, json=updates, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage
updated_agent = update_agent(
    "finance-reconciliation-001",
    your_token,
    config={
        "model": "gpt-4-turbo",
        "temperature": 0.5
    }
)
print(f"Updated agent config: {updated_agent['config']}")
```

### Delete Agent

**Python**:
```python
def delete_agent(agent_id, token):
    """Delete an agent (soft delete)."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.delete(url, headers=headers)
    response.raise_for_status()

    print(f"Agent {agent_id} deleted successfully")

# Example usage
delete_agent("finance-reconciliation-001", your_token)
```

## Memory Operations

### Query Agent Memory

**Python**:
```python
def query_memory(agent_id, query, memory_type=None, token=None):
    """Query agent's memory substrate."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}/memory"
    headers = {"Authorization": f"Bearer {token}"}

    params = {"query": query}
    if memory_type:
        params["memory_type"] = memory_type

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()

# Example usage
memories = query_memory(
    agent_id="finance-reconciliation-001",
    query="quarterly reconciliation process",
    memory_type="procedural",
    token=your_token
)

for memory in memories["memories"]:
    print(f"Memory ID: {memory['memory_id']}")
    print(f"Type: {memory['memory_type']}")
    print(f"Content: {memory['content']}")
    print("---")
```

### Store Memory

**Python**:
```python
def store_memory(agent_id, content, memory_type, metadata, token):
    """Store new memory in agent's substrate."""
    url = f"https://api.ants.ai/v1/agents/{agent_id}/memory"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "memory_type": memory_type,
        "content": content,
        "metadata": metadata
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage - Store episodic memory
memory = store_memory(
    agent_id="finance-reconciliation-001",
    content="Successfully reconciled Q4 2024 AP with 99.8% accuracy",
    memory_type="episodic",
    metadata={
        "quarter": "Q4_2024",
        "accuracy": 0.998,
        "discrepancies_found": 3
    },
    token=your_token
)

print(f"Stored memory ID: {memory['memory_id']}")
```

## Policy Management

### Create Policy

**Python**:
```python
def create_policy(name, description, rego_code, token):
    """Create a new OPA policy."""
    url = "https://api.ants.ai/v1/policies"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": name,
        "description": description,
        "rego_code": rego_code
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()

# Example usage - Policy to restrict finance agents to finance dept users
rego_policy = """
package ants.authz

import future.keywords.if

allow if {
    input.user.department == "finance"
    input.resource == "agent:finance"
    input.action == "execute"
}
"""

policy = create_policy(
    name="Finance Agent Access",
    description="Restrict finance agents to finance department users",
    rego_code=rego_policy,
    token=your_token
)

print(f"Created policy: {policy['policy_id']}")
```

## Monitoring

### Get CLEAR Metrics

**Python**:
```python
from datetime import datetime, timedelta

def get_metrics(token, agent_id=None, metric_type=None, hours=24):
    """Get CLEAR metrics for agents."""
    url = "https://api.ants.ai/v1/metrics"
    headers = {"Authorization": f"Bearer {token}"}

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    params = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }

    if agent_id:
        params["agent_id"] = agent_id
    if metric_type:
        params["metric_type"] = metric_type

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()

# Example usage
metrics = get_metrics(
    your_token,
    agent_id="finance-reconciliation-001",
    hours=24
)

m = metrics["metrics"]
print(f"Correctness: {m['correctness']*100:.1f}%")
print(f"Median Latency: {m['latency_p50']:.2f}s")
print(f"P95 Latency: {m['latency_p95']:.2f}s")
print(f"Efficiency: ${m['efficiency']:.4f} per task")
print(f"Availability: {m['availability']*100:.1f}%")
print(f"Resilience: {m['resilience']:.2f}s recovery")
```

## Error Handling

All errors follow RFC 7807 Problem Details format:

**Python**:
```python
import requests

try:
    response = requests.post(
        "https://api.ants.ai/v1/agents",
        json={"name": ""},  # Invalid - empty name
        headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    error = e.response.json()

    print(f"Error Type: {error['type']}")
    print(f"Title: {error['title']}")
    print(f"Status: {error['status']}")
    print(f"Detail: {error['detail']}")
    print(f"Instance: {error['instance']}")
```

**Common Error Responses**:

| Status | Type | Description |
|--------|------|-------------|
| 400 | `validation-error` | Invalid input data |
| 401 | `unauthorized` | Missing or invalid authentication |
| 403 | `forbidden` | Insufficient permissions |
| 404 | `not-found` | Resource doesn't exist |
| 429 | `rate-limit` | Rate limit exceeded |
| 500 | `internal-error` | Server error |

## Rate Limiting

API requests are rate limited per user and tenant.

**Rate Limit Headers**:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 2024-12-23T10:00:00Z
```

**Handling Rate Limits**:

**Python**:
```python
import time

def api_request_with_retry(url, token, max_retries=3):
    """Make API request with automatic retry on rate limit."""
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)

        if response.status_code == 429:
            # Rate limited
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Retrying after {retry_after}s...")
            time.sleep(retry_after)
            continue

        response.raise_for_status()
        return response.json()

    raise Exception("Max retries exceeded")
```

## Complete Example: Finance Reconciliation Workflow

```python
import requests
import time
from azure.identity import DefaultAzureCredential

class ANTSClient:
    """Simple ANTS API client."""

    def __init__(self, base_url="https://api.ants.ai/v1"):
        self.base_url = base_url
        credential = DefaultAzureCredential()
        token = credential.get_token("https://api.ants.ai/.default")
        self.headers = {"Authorization": f"Bearer {token.token}"}

    def create_agent(self, name, agent_type, specialization):
        response = requests.post(
            f"{self.base_url}/agents",
            json={"name": name, "type": agent_type, "specialization": specialization},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def execute_task(self, agent_id, task_description):
        response = requests.post(
            f"{self.base_url}/agents/{agent_id}/execute",
            json={"task_description": task_description},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_execution(self, execution_id):
        response = requests.get(
            f"{self.base_url}/executions/{execution_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def wait_for_completion(self, execution_id, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            exec_status = self.get_execution(execution_id)
            if exec_status["status"] == "completed":
                return exec_status
            elif exec_status["status"] == "failed":
                raise Exception(f"Execution failed: {exec_status['error']}")
            time.sleep(5)
        raise TimeoutError()

# Initialize client
client = ANTSClient()

# Create agent
print("Creating finance reconciliation agent...")
agent = client.create_agent(
    name="Q4 2024 Reconciliation Agent",
    agent_type="finance",
    specialization="accounts_payable_reconciliation"
)
print(f"✓ Created agent: {agent['agent_id']}")

# Execute task
print("\nExecuting reconciliation task...")
execution = client.execute_task(
    agent_id=agent["agent_id"],
    task_description="Reconcile accounts payable for Q4 2024, identify discrepancies, and generate summary report"
)
print(f"✓ Execution started: {execution['execution_id']}")

# Wait for completion
print("\nWaiting for completion...")
result = client.wait_for_completion(execution["execution_id"])

# Print results
print("\n=== Reconciliation Complete ===")
print(f"Status: {result['status']}")
print(f"Duration: {result['metrics']['duration_seconds']:.2f}s")
print(f"Cost: ${result['metrics']['cost_usd']:.4f}")
print(f"\nResult:")
print(result["result"])
```

## SDK Generation

Generate client SDKs from the OpenAPI spec:

```bash
# Python
openapi-generator generate -i docs/api/openapi.yaml -g python -o sdk/python

# JavaScript/TypeScript
openapi-generator generate -i docs/api/openapi.yaml -g typescript-axios -o sdk/typescript

# C#
openapi-generator generate -i docs/api/openapi.yaml -g csharp-netcore -o sdk/csharp

# Go
openapi-generator generate -i docs/api/openapi.yaml -g go -o sdk/go
```

## Testing

View the API documentation interactively:

```bash
# Install Swagger UI
npm install -g swagger-ui-cli

# Serve documentation
swagger-ui serve docs/api/openapi.yaml
# Opens http://localhost:8080
```

Or use Postman:

```bash
# Import OpenAPI spec into Postman
# File > Import > docs/api/openapi.yaml
```

## Support

- **Documentation**: https://docs.ants.ai
- **API Reference**: https://api.ants.ai/docs
- **Issues**: https://github.com/your-org/ants/issues
- **Email**: support@ants.ai
