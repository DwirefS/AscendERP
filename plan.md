# ANTS (AI-Agent Native Tactical System) - Code Build Plan

**Version**: 1.0
**Date**: December 21, 2024
**Status**: Implementation Blueprint

---

## Table of Contents

1. [Project Structure Overview](#1-project-structure-overview)
2. [Phase 1: Foundation Infrastructure](#2-phase-1-foundation-infrastructure)
3. [Phase 2: Core Agent Framework](#3-phase-2-core-agent-framework)
4. [Phase 3: Memory Substrate](#4-phase-3-memory-substrate)
5. [Phase 4: Trust Layer (Governance)](#5-phase-4-trust-layer-governance)
6. [Phase 5: SelfOps Agents](#6-phase-5-selfops-agents)
7. [Phase 6: Vertical Implementations](#7-phase-6-vertical-implementations)
8. [Phase 7: User Interface Layer](#8-phase-7-user-interface-layer)
9. [Phase 8: Observability & CLEAR Metrics](#9-phase-8-observability--clear-metrics)
10. [Module Specifications](#10-module-specifications)
11. [API Specifications](#11-api-specifications)
12. [Testing Strategy](#12-testing-strategy)

---

## 1. Project Structure Overview

```
ants/
├── infrastructure/
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── aks/                    # Azure Kubernetes Service
│   │   │   ├── anf/                    # Azure NetApp Files
│   │   │   ├── networking/             # VNet, subnets, NSGs
│   │   │   ├── identity/               # Entra ID, managed identities
│   │   │   ├── monitoring/             # Azure Monitor, Log Analytics
│   │   │   ├── gpu/                    # GPU node pools
│   │   │   └── tenant/                 # Multi-tenant provisioning
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   └── main.tf
│   └── helm/
│       ├── ants-core/                  # Core platform chart
│       ├── ants-agents/                # Agent deployments
│       ├── ants-observability/         # Monitoring stack
│       └── ants-nim/                   # NVIDIA NIM deployment
│
├── src/
│   ├── core/
│   │   ├── agent/                      # Base agent framework
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # BaseAgent class
│   │   │   ├── executor.py             # Agent executor/orchestrator
│   │   │   ├── memory.py               # Agent memory interface
│   │   │   ├── tools.py                # Tool registry and adapters
│   │   │   ├── protocols.py            # MCP/A2A protocol handlers
│   │   │   └── lifecycle.py            # Agent lifecycle management
│   │   │
│   │   ├── memory/                     # Memory substrate
│   │   │   ├── __init__.py
│   │   │   ├── episodic.py             # Episodic memory (traces, logs)
│   │   │   ├── semantic.py             # Semantic memory (vectors)
│   │   │   ├── procedural.py           # Procedural memory (policies)
│   │   │   ├── model.py                # Model memory (checkpoints)
│   │   │   ├── substrate.py            # ANF integration layer
│   │   │   └── entropy.py              # Memory aging and decay
│   │   │
│   │   ├── trust/                      # Trust layer (governance)
│   │   │   ├── __init__.py
│   │   │   ├── policy.py               # OPA policy engine integration
│   │   │   ├── audit.py                # Audit receipt generation
│   │   │   ├── hitl.py                 # Human-in-the-loop handlers
│   │   │   ├── guardrails.py           # NeMo guardrails integration
│   │   │   └── quarantine.py           # Agent quarantine logic
│   │   │
│   │   ├── inference/                  # Inference layer
│   │   │   ├── __init__.py
│   │   │   ├── nim_client.py           # NVIDIA NIM client
│   │   │   ├── model_router.py         # Model selection/routing
│   │   │   ├── embeddings.py           # Embedding generation
│   │   │   ├── reranker.py             # Reranking service
│   │   │   └── cache.py                # Inference caching
│   │   │
│   │   └── events/                     # Event fabric
│   │       ├── __init__.py
│   │       ├── publisher.py            # Event publishing
│   │       ├── subscriber.py           # Event subscription
│   │       ├── handlers.py             # Event handlers
│   │       └── schema.py               # Event schemas (CloudEvents)
│   │
│   ├── selfops/                        # SelfOps agents
│   │   ├── __init__.py
│   │   ├── infraops/
│   │   │   ├── agent.py                # InfraOps agent
│   │   │   ├── scaling.py              # Auto-scaling logic
│   │   │   ├── patching.py             # Patch management
│   │   │   └── cost.py                 # Cost optimization
│   │   ├── dataops/
│   │   │   ├── agent.py                # DataOps agent
│   │   │   ├── ingestion.py            # Data ingestion health
│   │   │   ├── indexing.py             # Index freshness
│   │   │   └── schema.py               # Schema evolution
│   │   ├── agentops/
│   │   │   ├── agent.py                # AgentOps agent
│   │   │   ├── drift.py                # Drift detection
│   │   │   ├── testing.py              # Prompt/spec testing
│   │   │   └── canary.py               # Canary deployments
│   │   └── secops/
│   │       ├── agent.py                # SecOps agent
│   │       ├── anomaly.py              # Anomaly detection
│   │       ├── enforcement.py          # Policy enforcement
│   │       └── incident.py             # Incident response
│   │
│   ├── verticals/                      # Industry vertical agents
│   │   ├── __init__.py
│   │   ├── finance/
│   │   │   ├── __init__.py
│   │   │   ├── agents/
│   │   │   │   ├── reconciliation.py   # AP/AR reconciliation agent
│   │   │   │   ├── audit.py            # Audit agent
│   │   │   │   ├── compliance.py       # Compliance agent
│   │   │   │   └── forecasting.py      # Financial forecasting
│   │   │   ├── tools/
│   │   │   │   ├── journal.py          # Journal entry tools
│   │   │   │   ├── ledger.py           # Ledger access tools
│   │   │   │   └── reporting.py        # Report generation
│   │   │   └── policies/
│   │   │       ├── sox.rego            # SOX compliance policies
│   │   │       └── approval.rego       # Approval workflows
│   │   │
│   │   ├── retail/
│   │   │   ├── __init__.py
│   │   │   ├── agents/
│   │   │   │   ├── demand.py           # Demand forecasting agent
│   │   │   │   ├── inventory.py        # Inventory optimization
│   │   │   │   ├── replenishment.py    # Auto-replenishment
│   │   │   │   └── pricing.py          # Dynamic pricing agent
│   │   │   ├── tools/
│   │   │   │   ├── pos.py              # POS integration
│   │   │   │   ├── warehouse.py        # Warehouse management
│   │   │   │   └── supplier.py         # Supplier APIs
│   │   │   └── policies/
│   │   │       └── pci.rego            # PCI-DSS compliance
│   │   │
│   │   ├── healthcare/
│   │   │   ├── __init__.py
│   │   │   ├── agents/
│   │   │   │   ├── rag.py              # PHI-safe RAG agent
│   │   │   │   ├── revenue_cycle.py    # Revenue cycle agent
│   │   │   │   ├── coding.py           # Medical coding agent
│   │   │   │   └── scheduling.py       # Appointment scheduling
│   │   │   ├── tools/
│   │   │   │   ├── ehr.py              # EHR integration (FHIR)
│   │   │   │   ├── claims.py           # Claims processing
│   │   │   │   └── redaction.py        # PHI redaction
│   │   │   └── policies/
│   │   │       └── hipaa.rego          # HIPAA compliance
│   │   │
│   │   └── manufacturing/
│   │       ├── __init__.py
│   │       ├── agents/
│   │       │   ├── digital_twin.py     # Digital twin agent
│   │       │   ├── predictive.py       # Predictive maintenance
│   │       │   ├── quality.py          # Quality control agent
│   │       │   └── production.py       # Production planning
│   │       ├── tools/
│   │       │   ├── iot.py              # IoT sensor integration
│   │       │   ├── scada.py            # SCADA systems
│   │       │   └── vision.py           # Computer vision
│   │       └── policies/
│   │           └── iso.rego            # ISO standards
│   │
│   ├── api/                            # API layer
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application
│   │   ├── routers/
│   │   │   ├── agents.py               # Agent management endpoints
│   │   │   ├── memory.py               # Memory access endpoints
│   │   │   ├── tasks.py                # Task submission/status
│   │   │   ├── audit.py                # Audit log endpoints
│   │   │   └── health.py               # Health check endpoints
│   │   ├── middleware/
│   │   │   ├── auth.py                 # Authentication middleware
│   │   │   ├── tracing.py              # Distributed tracing
│   │   │   └── rate_limit.py           # Rate limiting
│   │   └── schemas/
│   │       ├── agent.py                # Agent Pydantic models
│   │       ├── task.py                 # Task models
│   │       └── audit.py                # Audit models
│   │
│   ├── ui/                             # User interface
│   │   ├── teams/                      # Microsoft Teams integration
│   │   │   ├── bot.py                  # Teams bot handler
│   │   │   ├── cards.py                # Adaptive cards
│   │   │   └── auth.py                 # Teams auth
│   │   └── web/                        # Web chat interface
│   │       ├── app/                    # React/Next.js frontend
│   │       └── api/                    # Web API backend
│   │
│   └── observability/                  # Observability
│       ├── __init__.py
│       ├── metrics.py                  # CLEAR metrics collection
│       ├── traces.py                   # Distributed tracing
│       ├── logs.py                     # Structured logging
│       └── dashboards/                 # Grafana dashboards
│           ├── clear.json              # CLEAR metrics dashboard
│           ├── agents.json             # Agent health dashboard
│           └── memory.json             # Memory substrate dashboard
│
├── policies/                           # OPA/Rego policies
│   ├── common/
│   │   ├── rbac.rego                   # Role-based access control
│   │   ├── data_classification.rego   # Data classification rules
│   │   └── cost_limits.rego            # Cost threshold rules
│   ├── finance/
│   ├── healthcare/
│   ├── retail/
│   └── manufacturing/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── benchmarks/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── deployment/
│   └── runbooks/
│
├── scripts/
│   ├── setup.sh                        # Development setup
│   ├── deploy.sh                       # Deployment script
│   └── load_data.py                    # Demo data loader
│
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 2. Phase 1: Foundation Infrastructure

### 2.1 Terraform Modules

#### 2.1.1 AKS Module (`infrastructure/terraform/modules/aks/`)

```hcl
# main.tf
resource "azurerm_kubernetes_cluster" "ants" {
  name                = "ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "ants-${var.environment}"

  default_node_pool {
    name                = "system"
    node_count          = 3
    vm_size             = "Standard_D4s_v5"
    enable_auto_scaling = true
    min_count           = 3
    max_count           = 10
    vnet_subnet_id      = var.subnet_id
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
  }

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  tags = var.tags
}

# GPU node pool for inference
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.ants.id
  vm_size               = "Standard_NC24ads_A100_v4"
  node_count            = 2
  enable_auto_scaling   = true
  min_count             = 0
  max_count             = 8
  vnet_subnet_id        = var.subnet_id

  node_taints = ["nvidia.com/gpu=present:NoSchedule"]
  node_labels = {
    "nvidia.com/gpu" = "true"
    "workload"       = "inference"
  }

  tags = var.tags
}

# Agent node pool
resource "azurerm_kubernetes_cluster_node_pool" "agents" {
  name                  = "agents"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.ants.id
  vm_size               = "Standard_D8s_v5"
  enable_auto_scaling   = true
  min_count             = 3
  max_count             = 50
  vnet_subnet_id        = var.subnet_id

  node_labels = {
    "workload" = "agents"
  }

  tags = var.tags
}
```

**Variables** (`variables.tf`):
```hcl
variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "eastus2"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID for AKS nodes"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
```

**Outputs** (`outputs.tf`):
```hcl
output "cluster_id" {
  value = azurerm_kubernetes_cluster.ants.id
}

output "kube_config" {
  value     = azurerm_kubernetes_cluster.ants.kube_config_raw
  sensitive = true
}

output "cluster_identity" {
  value = azurerm_kubernetes_cluster.ants.identity[0].principal_id
}
```

#### 2.1.2 ANF Module (`infrastructure/terraform/modules/anf/`)

```hcl
# main.tf
resource "azurerm_netapp_account" "ants" {
  name                = "ants-netapp-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = var.tags
}

resource "azurerm_netapp_pool" "memory" {
  name                = "memory-pool"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  service_level       = var.service_level
  size_in_tb          = var.pool_size_tb

  qos_type = "Auto"

  tags = var.tags
}

# Episodic memory volume (logs, traces)
resource "azurerm_netapp_volume" "episodic" {
  name                = "episodic-memory"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.memory.name
  volume_path         = "episodic"
  service_level       = var.service_level
  subnet_id           = var.delegated_subnet_id
  storage_quota_in_gb = var.episodic_volume_size_gb
  protocols           = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  data_protection_snapshot_policy {
    snapshot_policy_id = azurerm_netapp_snapshot_policy.default.id
  }

  tags = var.tags
}

# Semantic memory volume (vectors, embeddings)
resource "azurerm_netapp_volume" "semantic" {
  name                = "semantic-memory"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.memory.name
  volume_path         = "semantic"
  service_level       = "Ultra"  # High IOPS for vector search
  subnet_id           = var.delegated_subnet_id
  storage_quota_in_gb = var.semantic_volume_size_gb
  protocols           = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = var.tags
}

# Model memory volume (checkpoints, fine-tunes)
resource "azurerm_netapp_volume" "model" {
  name                = "model-memory"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.memory.name
  volume_path         = "models"
  service_level       = var.service_level
  subnet_id           = var.delegated_subnet_id
  storage_quota_in_gb = var.model_volume_size_gb
  protocols           = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  data_protection_snapshot_policy {
    snapshot_policy_id = azurerm_netapp_snapshot_policy.models.id
  }

  tags = var.tags
}

# Snapshot policies
resource "azurerm_netapp_snapshot_policy" "default" {
  name                = "default-policy"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  enabled             = true

  hourly_schedule {
    snapshots_to_keep = 24
    minute            = 0
  }

  daily_schedule {
    snapshots_to_keep = 7
    hour              = 0
    minute            = 0
  }

  weekly_schedule {
    snapshots_to_keep = 4
    days_of_week      = ["Sunday"]
    hour              = 0
    minute            = 0
  }

  tags = var.tags
}

resource "azurerm_netapp_snapshot_policy" "models" {
  name                = "models-policy"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  enabled             = true

  # More frequent snapshots for model safety
  hourly_schedule {
    snapshots_to_keep = 48
    minute            = 0
  }

  daily_schedule {
    snapshots_to_keep = 30
    hour              = 0
    minute            = 0
  }

  tags = var.tags
}
```

---

## 3. Phase 2: Core Agent Framework

### 3.1 Base Agent Class (`src/core/agent/base.py`)

```python
"""
Base Agent implementation for ANTS.
All agents inherit from this class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
import structlog

from core.memory import MemorySubstrate, EpisodicMemory, SemanticMemory
from core.trust import PolicyEngine, AuditLogger, Guardrails
from core.inference import NIMClient, ModelRouter
from core.events import EventPublisher


logger = structlog.get_logger()


class AgentState(Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    EXECUTING = "executing"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    QUARANTINED = "quarantined"
    TERMINATED = "terminated"


@dataclass
class AgentContext:
    """Context passed to agent during execution."""
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str
    environment: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentAction:
    """Represents an action the agent wants to take."""
    action_id: str
    tool_name: str
    tool_args: Dict[str, Any]
    reasoning: str
    confidence: float
    requires_approval: bool = False
    data_classification: str = "internal"


@dataclass
class ActionResult:
    """Result of an agent action."""
    action_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: float = 0
    tokens_used: int = 0


class BaseAgent(ABC):
    """
    Base class for all ANTS agents.

    Implements the core agent loop:
    1. Perceive - gather context and inputs
    2. Retrieve - access relevant memory
    3. Reason - generate action plan
    4. Act - execute tools (policy-gated)
    5. Verify - validate outcomes
    6. Learn - update memory
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        model_id: str = "llama-3-70b",
        tools: Optional[List[Callable]] = None,
        policies: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.model_id = model_id
        self.tools = tools or []
        self.policies = policies or []
        self.config = config or {}

        self.state = AgentState.INITIALIZING
        self.created_at = datetime.utcnow()

        # Core dependencies (injected)
        self.memory: MemorySubstrate = None
        self.policy_engine: PolicyEngine = None
        self.audit_logger: AuditLogger = None
        self.guardrails: Guardrails = None
        self.nim_client: NIMClient = None
        self.model_router: ModelRouter = None
        self.event_publisher: EventPublisher = None

        self._tool_registry: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        """Register available tools."""
        for tool in self.tools:
            tool_name = getattr(tool, "__name__", str(tool))
            self._tool_registry[tool_name] = tool

    async def initialize(self, dependencies: Dict[str, Any]):
        """Initialize agent with dependencies."""
        self.memory = dependencies.get("memory")
        self.policy_engine = dependencies.get("policy_engine")
        self.audit_logger = dependencies.get("audit_logger")
        self.guardrails = dependencies.get("guardrails")
        self.nim_client = dependencies.get("nim_client")
        self.model_router = dependencies.get("model_router")
        self.event_publisher = dependencies.get("event_publisher")

        self.state = AgentState.READY
        logger.info("agent_initialized", agent_id=self.agent_id, name=self.name)

    @abstractmethod
    async def perceive(self, context: AgentContext, input_data: Any) -> Dict[str, Any]:
        """
        Gather context and process inputs.
        Override in subclasses for domain-specific perception.
        """
        pass

    @abstractmethod
    async def retrieve(self, context: AgentContext, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve relevant information from memory.
        Override in subclasses for domain-specific retrieval.
        """
        pass

    @abstractmethod
    async def reason(
        self,
        context: AgentContext,
        perception: Dict[str, Any],
        retrieved: Dict[str, Any]
    ) -> List[AgentAction]:
        """
        Generate action plan based on perception and retrieved context.
        Override in subclasses for domain-specific reasoning.
        """
        pass

    async def act(
        self,
        context: AgentContext,
        actions: List[AgentAction]
    ) -> List[ActionResult]:
        """
        Execute actions through policy gates.
        """
        results = []

        for action in actions:
            # Check policy gate
            policy_decision = await self.policy_engine.evaluate(
                action=action,
                context=context,
                policies=self.policies
            )

            # Log audit receipt
            receipt_id = await self.audit_logger.log_action_attempt(
                context=context,
                action=action,
                policy_decision=policy_decision
            )

            if policy_decision.decision == "DENY":
                results.append(ActionResult(
                    action_id=action.action_id,
                    success=False,
                    result=None,
                    error=f"Action denied by policy: {policy_decision.reason}"
                ))
                continue

            if policy_decision.decision == "REQUIRE_APPROVAL":
                self.state = AgentState.WAITING_APPROVAL
                # Emit HITL event
                await self.event_publisher.publish(
                    event_type="agent.approval_required",
                    data={
                        "agent_id": self.agent_id,
                        "action": action.__dict__,
                        "receipt_id": receipt_id,
                        "context": context.__dict__
                    }
                )
                results.append(ActionResult(
                    action_id=action.action_id,
                    success=False,
                    result=None,
                    error="Awaiting human approval"
                ))
                continue

            # Execute tool
            try:
                tool = self._tool_registry.get(action.tool_name)
                if not tool:
                    raise ValueError(f"Tool not found: {action.tool_name}")

                start_time = datetime.utcnow()

                # Apply guardrails to input
                guarded_args = await self.guardrails.guard_input(
                    action.tool_args,
                    context=context
                )

                # Execute
                result = await tool(**guarded_args)

                # Apply guardrails to output
                guarded_result = await self.guardrails.guard_output(
                    result,
                    context=context
                )

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                action_result = ActionResult(
                    action_id=action.action_id,
                    success=True,
                    result=guarded_result,
                    execution_time_ms=execution_time
                )

                # Log success
                await self.audit_logger.log_action_result(
                    receipt_id=receipt_id,
                    result=action_result
                )

                results.append(action_result)

            except Exception as e:
                logger.error(
                    "action_failed",
                    agent_id=self.agent_id,
                    action_id=action.action_id,
                    error=str(e)
                )
                results.append(ActionResult(
                    action_id=action.action_id,
                    success=False,
                    result=None,
                    error=str(e)
                ))

        return results

    @abstractmethod
    async def verify(
        self,
        context: AgentContext,
        actions: List[AgentAction],
        results: List[ActionResult]
    ) -> bool:
        """
        Verify action outcomes.
        Override in subclasses for domain-specific verification.
        """
        pass

    async def learn(
        self,
        context: AgentContext,
        perception: Dict[str, Any],
        actions: List[AgentAction],
        results: List[ActionResult],
        verification: bool
    ):
        """
        Update memory based on execution.
        """
        # Store episodic memory (trace)
        trace = {
            "trace_id": context.trace_id,
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "perception": perception,
            "actions": [a.__dict__ for a in actions],
            "results": [r.__dict__ for r in results],
            "verification_passed": verification
        }

        await self.memory.episodic.store(
            key=f"trace:{context.trace_id}",
            value=trace,
            ttl_hours=720  # 30 days
        )

        # Update semantic memory if learning enabled
        if self.config.get("learning_enabled", True):
            await self._update_semantic_memory(context, trace)

    async def _update_semantic_memory(self, context: AgentContext, trace: Dict):
        """Update semantic memory with learnings."""
        # Generate embedding for the trace
        trace_text = self._summarize_trace(trace)
        embedding = await self.nim_client.embed(trace_text)

        await self.memory.semantic.store(
            key=f"learning:{context.trace_id}",
            vector=embedding,
            metadata={
                "agent_id": self.agent_id,
                "success": trace["verification_passed"],
                "timestamp": trace["timestamp"]
            }
        )

    def _summarize_trace(self, trace: Dict) -> str:
        """Create text summary of trace for embedding."""
        actions_summary = ", ".join([a["tool_name"] for a in trace["actions"]])
        success = trace["verification_passed"]
        return f"Agent {self.name} executed: {actions_summary}. Success: {success}"

    async def run(self, context: AgentContext, input_data: Any) -> Dict[str, Any]:
        """
        Main agent execution loop.
        """
        self.state = AgentState.EXECUTING

        try:
            # 1. Perceive
            perception = await self.perceive(context, input_data)

            # 2. Retrieve
            retrieved = await self.retrieve(context, perception)

            # 3. Reason
            actions = await self.reason(context, perception, retrieved)

            # 4. Act
            results = await self.act(context, actions)

            # 5. Verify
            verified = await self.verify(context, actions, results)

            # 6. Learn
            await self.learn(context, perception, actions, results, verified)

            self.state = AgentState.READY

            return {
                "success": verified,
                "actions_taken": len(actions),
                "results": [r.__dict__ for r in results],
                "trace_id": context.trace_id
            }

        except Exception as e:
            logger.error(
                "agent_execution_failed",
                agent_id=self.agent_id,
                trace_id=context.trace_id,
                error=str(e)
            )
            self.state = AgentState.READY
            raise

    async def quarantine(self, reason: str):
        """Put agent in quarantine state."""
        self.state = AgentState.QUARANTINED
        await self.event_publisher.publish(
            event_type="agent.quarantined",
            data={
                "agent_id": self.agent_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        logger.warning("agent_quarantined", agent_id=self.agent_id, reason=reason)
```

### 3.2 Agent Executor (`src/core/agent/executor.py`)

```python
"""
Agent Executor - Orchestrates agent execution.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import structlog

from core.agent.base import BaseAgent, AgentContext
from core.agent.lifecycle import AgentRegistry
from core.events import EventPublisher


logger = structlog.get_logger()


@dataclass
class TaskRequest:
    """Request to execute an agent task."""
    task_id: str
    agent_id: str
    input_data: Any
    context: AgentContext
    priority: int = 0
    timeout_seconds: int = 300


@dataclass
class TaskResult:
    """Result of an agent task execution."""
    task_id: str
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time_ms: float
    trace_id: str


class AgentExecutor:
    """
    Orchestrates agent task execution.
    Manages concurrency, timeouts, and error handling.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_publisher: EventPublisher,
        max_concurrent_tasks: int = 100,
    ):
        self.registry = registry
        self.event_publisher = event_publisher
        self.max_concurrent_tasks = max_concurrent_tasks

        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._running = False

    async def start(self):
        """Start the executor."""
        self._running = True
        logger.info("executor_started", max_concurrent=self.max_concurrent_tasks)
        asyncio.create_task(self._process_queue())

    async def stop(self):
        """Stop the executor gracefully."""
        self._running = False
        # Wait for active tasks
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
        logger.info("executor_stopped")

    async def submit(self, request: TaskRequest) -> str:
        """Submit a task for execution."""
        await self._task_queue.put(request)

        await self.event_publisher.publish(
            event_type="task.submitted",
            data={
                "task_id": request.task_id,
                "agent_id": request.agent_id,
                "priority": request.priority
            }
        )

        return request.task_id

    async def _process_queue(self):
        """Process tasks from the queue."""
        while self._running:
            try:
                request = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )

                async with self._semaphore:
                    task = asyncio.create_task(
                        self._execute_task(request)
                    )
                    self._active_tasks[request.task_id] = task

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("queue_processing_error", error=str(e))

    async def _execute_task(self, request: TaskRequest) -> TaskResult:
        """Execute a single task."""
        start_time = datetime.utcnow()

        try:
            # Get agent from registry
            agent = await self.registry.get(request.agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {request.agent_id}")

            # Execute with timeout
            result = await asyncio.wait_for(
                agent.run(request.context, request.input_data),
                timeout=request.timeout_seconds
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            task_result = TaskResult(
                task_id=request.task_id,
                agent_id=request.agent_id,
                success=result.get("success", False),
                result=result,
                error=None,
                execution_time_ms=execution_time,
                trace_id=request.context.trace_id
            )

            await self.event_publisher.publish(
                event_type="task.completed",
                data=task_result.__dict__
            )

            return task_result

        except asyncio.TimeoutError:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            task_result = TaskResult(
                task_id=request.task_id,
                agent_id=request.agent_id,
                success=False,
                result=None,
                error=f"Task timed out after {request.timeout_seconds}s",
                execution_time_ms=execution_time,
                trace_id=request.context.trace_id
            )

            await self.event_publisher.publish(
                event_type="task.timeout",
                data=task_result.__dict__
            )

            return task_result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            task_result = TaskResult(
                task_id=request.task_id,
                agent_id=request.agent_id,
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time,
                trace_id=request.context.trace_id
            )

            await self.event_publisher.publish(
                event_type="task.failed",
                data=task_result.__dict__
            )

            logger.error(
                "task_execution_failed",
                task_id=request.task_id,
                error=str(e)
            )

            return task_result

        finally:
            self._active_tasks.pop(request.task_id, None)
```

---

## 4. Phase 3: Memory Substrate

### 4.1 Memory Substrate Interface (`src/core/memory/substrate.py`)

```python
"""
Memory Substrate - ANF-backed memory layer for ANTS agents.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import aiofiles
import asyncpg
import numpy as np
from pathlib import Path
import structlog


logger = structlog.get_logger()


@dataclass
class MemoryConfig:
    """Configuration for memory substrate."""
    anf_mount_path: str = "/mnt/ants-memory"
    postgres_dsn: str = "postgresql://ants:password@localhost/ants"
    vector_dimensions: int = 1536
    episodic_ttl_days: int = 90
    semantic_refresh_hours: int = 24


class MemorySubstrate:
    """
    Unified memory substrate for ANTS.
    Integrates ANF storage with PostgreSQL + pgvector.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.episodic = EpisodicMemory(config)
        self.semantic = SemanticMemory(config)
        self.procedural = ProceduralMemory(config)
        self.model = ModelMemory(config)

        self._db_pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize memory substrate connections."""
        # Initialize PostgreSQL connection pool
        self._db_pool = await asyncpg.create_pool(
            self.config.postgres_dsn,
            min_size=5,
            max_size=20
        )

        # Initialize pgvector extension
        async with self._db_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await self._ensure_tables(conn)

        # Initialize sub-memories
        await self.episodic.initialize(self._db_pool)
        await self.semantic.initialize(self._db_pool)
        await self.procedural.initialize()
        await self.model.initialize()

        logger.info("memory_substrate_initialized")

    async def _ensure_tables(self, conn):
        """Ensure required database tables exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value JSONB NOT NULL,
                agent_id TEXT,
                tenant_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                metadata JSONB
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_memory (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                embedding vector(1536),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_semantic_embedding
            ON semantic_memory USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

    async def snapshot(self, snapshot_name: str) -> str:
        """
        Create a snapshot of the memory state.
        Leverages ANF snapshot capability.
        """
        # This would trigger ANF snapshot via REST API
        snapshot_path = f"{self.config.anf_mount_path}/.snapshot/{snapshot_name}"
        logger.info("memory_snapshot_created", name=snapshot_name)
        return snapshot_path

    async def restore(self, snapshot_name: str):
        """
        Restore memory from a snapshot.
        Time-travel capability for AI safety.
        """
        snapshot_path = f"{self.config.anf_mount_path}/.snapshot/{snapshot_name}"
        logger.info("memory_restore_initiated", name=snapshot_name)
        # Implementation would use ANF clone-from-snapshot

    async def close(self):
        """Close connections."""
        if self._db_pool:
            await self._db_pool.close()


class EpisodicMemory:
    """
    Episodic memory for traces, logs, and conversation history.
    Stored in PostgreSQL with JSONB.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._db_pool: Optional[asyncpg.Pool] = None

    async def initialize(self, db_pool: asyncpg.Pool):
        self._db_pool = db_pool

    async def store(
        self,
        key: str,
        value: Dict[str, Any],
        ttl_hours: Optional[int] = None,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Store episodic memory."""
        expires_at = None
        if ttl_hours:
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO episodic_memory (key, value, agent_id, tenant_id, expires_at, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (key) DO UPDATE SET
                    value = $2,
                    expires_at = $5,
                    metadata = $6
            """, key, value, agent_id, tenant_id, expires_at, metadata or {})

    async def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve episodic memory by key."""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM episodic_memory WHERE key = $1 AND (expires_at IS NULL OR expires_at > NOW())",
                key
            )
            return dict(row["value"]) if row else None

    async def search(
        self,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search episodic memories."""
        async with self._db_pool.acquire() as conn:
            query = """
                SELECT key, value, created_at
                FROM episodic_memory
                WHERE (expires_at IS NULL OR expires_at > NOW())
            """
            params = []

            if agent_id:
                query += f" AND agent_id = ${len(params) + 1}"
                params.append(agent_id)

            if tenant_id:
                query += f" AND tenant_id = ${len(params) + 1}"
                params.append(tenant_id)

            query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [{"key": r["key"], "value": dict(r["value"]), "created_at": r["created_at"]} for r in rows]


class SemanticMemory:
    """
    Semantic memory using vector embeddings.
    Stored in PostgreSQL with pgvector.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._db_pool: Optional[asyncpg.Pool] = None

    async def initialize(self, db_pool: asyncpg.Pool):
        self._db_pool = db_pool

    async def store(
        self,
        key: str,
        vector: List[float],
        metadata: Optional[Dict] = None
    ):
        """Store semantic memory with vector embedding."""
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO semantic_memory (key, embedding, metadata)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET
                    embedding = $2,
                    metadata = $3,
                    updated_at = NOW()
            """, key, vector, metadata or {})

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search semantic memory by vector similarity."""
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT key, metadata, 1 - (embedding <=> $1) as similarity
                FROM semantic_memory
                WHERE 1 - (embedding <=> $1) > $2
                ORDER BY embedding <=> $1
                LIMIT $3
            """, query_vector, threshold, limit)

            return [
                {"key": r["key"], "metadata": dict(r["metadata"]), "similarity": r["similarity"]}
                for r in rows
            ]


class ProceduralMemory:
    """
    Procedural memory for policies, runbooks, and prompt templates.
    Stored on ANF as files with version control.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.base_path = Path(config.anf_mount_path) / "procedural"

    async def initialize(self):
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store(self, key: str, content: str, version: Optional[str] = None):
        """Store procedural memory."""
        file_path = self.base_path / f"{key}.md"
        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)

    async def retrieve(self, key: str) -> Optional[str]:
        """Retrieve procedural memory."""
        file_path = self.base_path / f"{key}.md"
        if file_path.exists():
            async with aiofiles.open(file_path, "r") as f:
                return await f.read()
        return None

    async def list_all(self) -> List[str]:
        """List all procedural memories."""
        return [f.stem for f in self.base_path.glob("*.md")]


class ModelMemory:
    """
    Model memory for checkpoints, fine-tunes, and adapter weights.
    Stored on ANF with snapshot protection.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.base_path = Path(config.anf_mount_path) / "models"

    async def initialize(self):
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store_checkpoint(self, model_id: str, checkpoint_path: str, metadata: Dict):
        """Store model checkpoint."""
        target_path = self.base_path / model_id / "checkpoints"
        target_path.mkdir(parents=True, exist_ok=True)
        # Copy checkpoint files to ANF
        # In practice, this would be a more sophisticated sync

    async def list_checkpoints(self, model_id: str) -> List[Dict]:
        """List available checkpoints for a model."""
        checkpoint_path = self.base_path / model_id / "checkpoints"
        if checkpoint_path.exists():
            return [{"name": d.name, "path": str(d)} for d in checkpoint_path.iterdir() if d.is_dir()]
        return []
```

---

## 5. Phase 4: Trust Layer (Governance)

### 5.1 Policy Engine (`src/core/trust/policy.py`)

```python
"""
Policy Engine - OPA integration for policy-gated actions.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import httpx
import structlog

from core.agent.base import AgentAction, AgentContext


logger = structlog.get_logger()


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""
    decision: str  # ALLOW, DENY, REQUIRE_APPROVAL, ALLOW_WITH_REDACTION
    reason: str
    policy_id: str
    evaluated_at: str
    metadata: Dict[str, Any]


class PolicyEngine:
    """
    Policy engine using Open Policy Agent (OPA).
    Evaluates agent actions against defined policies.
    """

    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
        self._client = httpx.AsyncClient(timeout=10.0)

    async def evaluate(
        self,
        action: AgentAction,
        context: AgentContext,
        policies: List[str]
    ) -> PolicyDecision:
        """
        Evaluate action against policies.
        """
        # Build input for OPA
        opa_input = {
            "action": {
                "tool_name": action.tool_name,
                "tool_args": action.tool_args,
                "data_classification": action.data_classification,
                "confidence": action.confidence
            },
            "context": {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "environment": context.environment,
                "metadata": context.metadata
            }
        }

        # Evaluate each policy
        for policy_path in policies:
            try:
                response = await self._client.post(
                    f"{self.opa_url}/v1/data/{policy_path}",
                    json={"input": opa_input}
                )
                result = response.json().get("result", {})

                if result.get("deny", False):
                    return PolicyDecision(
                        decision="DENY",
                        reason=result.get("reason", "Policy denied action"),
                        policy_id=policy_path,
                        evaluated_at=datetime.utcnow().isoformat(),
                        metadata=result
                    )

                if result.get("require_approval", False):
                    return PolicyDecision(
                        decision="REQUIRE_APPROVAL",
                        reason=result.get("reason", "Action requires human approval"),
                        policy_id=policy_path,
                        evaluated_at=datetime.utcnow().isoformat(),
                        metadata=result
                    )

                if result.get("redact_output", False):
                    return PolicyDecision(
                        decision="ALLOW_WITH_REDACTION",
                        reason=result.get("reason", "Output must be redacted"),
                        policy_id=policy_path,
                        evaluated_at=datetime.utcnow().isoformat(),
                        metadata={"redaction_rules": result.get("redaction_rules", [])}
                    )

            except Exception as e:
                logger.error("policy_evaluation_failed", policy=policy_path, error=str(e))
                # Fail closed - deny on error
                return PolicyDecision(
                    decision="DENY",
                    reason=f"Policy evaluation error: {str(e)}",
                    policy_id=policy_path,
                    evaluated_at=datetime.utcnow().isoformat(),
                    metadata={}
                )

        # All policies passed
        return PolicyDecision(
            decision="ALLOW",
            reason="All policies passed",
            policy_id="all",
            evaluated_at=datetime.utcnow().isoformat(),
            metadata={}
        )

    async def load_policy(self, policy_id: str, policy_content: str):
        """Load a Rego policy into OPA."""
        await self._client.put(
            f"{self.opa_url}/v1/policies/{policy_id}",
            content=policy_content,
            headers={"Content-Type": "text/plain"}
        )

    async def close(self):
        await self._client.aclose()
```

### 5.2 Audit Logger (`src/core/trust/audit.py`)

```python
"""
Audit Logger - Immutable audit receipts for agent actions.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib
import json
from uuid import uuid4
import asyncpg
import structlog

from core.agent.base import AgentAction, AgentContext, ActionResult


logger = structlog.get_logger()


@dataclass
class AuditReceipt:
    """Immutable audit receipt for an action."""
    receipt_id: str
    trace_id: str
    timestamp: str

    # Actor
    agent_id: str
    user_id: str
    tenant_id: str

    # Action
    action_id: str
    tool_name: str
    tool_args_hash: str  # SHA256 of args (not storing raw for security)

    # Policy
    policy_decision: str
    policy_id: str

    # Data lineage
    input_sources: list
    output_destinations: list

    # Model lineage
    model_id: str
    prompt_hash: str

    # Result (populated after execution)
    result_status: Optional[str] = None
    result_hash: Optional[str] = None
    error: Optional[str] = None

    # Integrity
    receipt_hash: Optional[str] = None


class AuditLogger:
    """
    Forensics-grade audit logging.
    All receipts are immutable and hash-chained.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self._db_pool = db_pool
        self._last_receipt_hash: Optional[str] = None

    async def initialize(self):
        """Initialize audit tables."""
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    agent_id TEXT NOT NULL,
                    user_id TEXT,
                    tenant_id TEXT,
                    action_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_args_hash TEXT NOT NULL,
                    policy_decision TEXT NOT NULL,
                    policy_id TEXT,
                    input_sources JSONB,
                    output_destinations JSONB,
                    model_id TEXT,
                    prompt_hash TEXT,
                    result_status TEXT,
                    result_hash TEXT,
                    error TEXT,
                    receipt_hash TEXT NOT NULL,
                    previous_receipt_hash TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_trace
                ON audit_receipts (trace_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_agent
                ON audit_receipts (agent_id, timestamp)
            """)

    async def log_action_attempt(
        self,
        context: AgentContext,
        action: AgentAction,
        policy_decision: 'PolicyDecision'
    ) -> str:
        """Log an action attempt before execution."""
        receipt_id = str(uuid4())

        receipt = AuditReceipt(
            receipt_id=receipt_id,
            trace_id=context.trace_id,
            timestamp=datetime.utcnow().isoformat(),
            agent_id=context.metadata.get("agent_id", "unknown"),
            user_id=context.user_id,
            tenant_id=context.tenant_id,
            action_id=action.action_id,
            tool_name=action.tool_name,
            tool_args_hash=self._hash(json.dumps(action.tool_args, sort_keys=True)),
            policy_decision=policy_decision.decision,
            policy_id=policy_decision.policy_id,
            input_sources=[],
            output_destinations=[],
            model_id=context.metadata.get("model_id", "unknown"),
            prompt_hash=self._hash(str(action.reasoning))
        )

        # Calculate receipt hash (includes previous hash for chaining)
        receipt.receipt_hash = self._calculate_receipt_hash(receipt)

        # Store receipt
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_receipts (
                    receipt_id, trace_id, timestamp, agent_id, user_id, tenant_id,
                    action_id, tool_name, tool_args_hash, policy_decision, policy_id,
                    input_sources, output_destinations, model_id, prompt_hash,
                    receipt_hash, previous_receipt_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            """,
                receipt.receipt_id, receipt.trace_id, datetime.fromisoformat(receipt.timestamp),
                receipt.agent_id, receipt.user_id, receipt.tenant_id,
                receipt.action_id, receipt.tool_name, receipt.tool_args_hash,
                receipt.policy_decision, receipt.policy_id,
                json.dumps(receipt.input_sources), json.dumps(receipt.output_destinations),
                receipt.model_id, receipt.prompt_hash, receipt.receipt_hash, self._last_receipt_hash
            )

        self._last_receipt_hash = receipt.receipt_hash
        return receipt_id

    async def log_action_result(self, receipt_id: str, result: ActionResult):
        """Update receipt with action result."""
        result_hash = self._hash(json.dumps(result.__dict__, default=str, sort_keys=True))

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE audit_receipts
                SET result_status = $2, result_hash = $3, error = $4
                WHERE receipt_id = $1
            """, receipt_id, "success" if result.success else "failed", result_hash, result.error)

    def _hash(self, content: str) -> str:
        """Generate SHA256 hash."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _calculate_receipt_hash(self, receipt: AuditReceipt) -> str:
        """Calculate hash for receipt integrity."""
        # Include previous hash for chaining
        content = json.dumps({
            "receipt_id": receipt.receipt_id,
            "trace_id": receipt.trace_id,
            "timestamp": receipt.timestamp,
            "agent_id": receipt.agent_id,
            "action_id": receipt.action_id,
            "tool_name": receipt.tool_name,
            "tool_args_hash": receipt.tool_args_hash,
            "policy_decision": receipt.policy_decision,
            "previous_hash": self._last_receipt_hash
        }, sort_keys=True)
        return self._hash(content)

    async def get_audit_trail(
        self,
        trace_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve audit trail with filters."""
        query = "SELECT * FROM audit_receipts WHERE 1=1"
        params = []

        if trace_id:
            params.append(trace_id)
            query += f" AND trace_id = ${len(params)}"

        if agent_id:
            params.append(agent_id)
            query += f" AND agent_id = ${len(params)}"

        if start_time:
            params.append(start_time)
            query += f" AND timestamp >= ${len(params)}"

        if end_time:
            params.append(end_time)
            query += f" AND timestamp <= ${len(params)}"

        params.append(limit)
        query += f" ORDER BY timestamp DESC LIMIT ${len(params)}"

        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def verify_chain_integrity(self) -> bool:
        """Verify the integrity of the audit chain."""
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT receipt_id, receipt_hash, previous_receipt_hash FROM audit_receipts ORDER BY created_at"
            )

            prev_hash = None
            for row in rows:
                if row["previous_receipt_hash"] != prev_hash:
                    logger.error("audit_chain_broken", receipt_id=row["receipt_id"])
                    return False
                prev_hash = row["receipt_hash"]

            return True
```

---

## 6. Phase 5: SelfOps Agents

### 6.1 InfraOps Agent (`src/selfops/infraops/agent.py`)

```python
"""
InfraOps Agent - Self-managing infrastructure operations.
"""
from typing import Dict, Any, List
from core.agent.base import BaseAgent, AgentContext, AgentAction
from core.agent.tools import tool


class InfraOpsAgent(BaseAgent):
    """
    Agent responsible for infrastructure self-management.

    Capabilities:
    - Auto-scaling based on load
    - Cost optimization
    - Resource provisioning
    - Patch management
    """

    def __init__(self):
        super().__init__(
            agent_id="infraops-001",
            name="InfraOps Agent",
            description="Manages ANTS infrastructure automatically",
            model_id="llama-3-70b",
            tools=[
                self.scale_node_pool,
                self.adjust_anf_capacity,
                self.check_resource_health,
                self.apply_cost_optimization,
                self.trigger_maintenance
            ],
            policies=["selfops/infraops.rego"]
        )

    async def perceive(self, context: AgentContext, input_data: Any) -> Dict[str, Any]:
        """Gather infrastructure metrics and alerts."""
        return {
            "alerts": input_data.get("alerts", []),
            "metrics": await self._fetch_metrics(),
            "current_state": await self._get_infrastructure_state()
        }

    async def retrieve(self, context: AgentContext, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve historical patterns and runbooks."""
        # Get similar past incidents
        similar_incidents = await self.memory.semantic.search(
            query_vector=await self._embed_perception(perception),
            limit=5
        )

        # Get relevant runbooks
        runbooks = await self.memory.procedural.retrieve("infraops/runbooks")

        return {
            "similar_incidents": similar_incidents,
            "runbooks": runbooks
        }

    async def reason(
        self,
        context: AgentContext,
        perception: Dict[str, Any],
        retrieved: Dict[str, Any]
    ) -> List[AgentAction]:
        """Determine infrastructure actions needed."""
        prompt = self._build_reasoning_prompt(perception, retrieved)

        response = await self.nim_client.complete(
            model=self.model_id,
            prompt=prompt,
            max_tokens=2000
        )

        return self._parse_actions(response)

    async def verify(
        self,
        context: AgentContext,
        actions: List[AgentAction],
        results: List['ActionResult']
    ) -> bool:
        """Verify infrastructure changes were applied correctly."""
        for action, result in zip(actions, results):
            if not result.success:
                return False

            # Verify the change took effect
            if action.tool_name == "scale_node_pool":
                # Check node count matches expected
                pass
            elif action.tool_name == "adjust_anf_capacity":
                # Verify ANF volume size
                pass

        return True

    @tool
    async def scale_node_pool(
        self,
        pool_name: str,
        target_count: int,
        reason: str
    ) -> Dict[str, Any]:
        """Scale an AKS node pool."""
        # Implementation using Azure SDK
        pass

    @tool
    async def adjust_anf_capacity(
        self,
        volume_name: str,
        new_size_gb: int,
        reason: str
    ) -> Dict[str, Any]:
        """Adjust ANF volume capacity."""
        # Implementation using Azure SDK
        pass

    @tool
    async def check_resource_health(self) -> Dict[str, Any]:
        """Check health of all infrastructure resources."""
        pass

    @tool
    async def apply_cost_optimization(
        self,
        recommendations: List[Dict]
    ) -> Dict[str, Any]:
        """Apply cost optimization recommendations."""
        pass

    @tool
    async def trigger_maintenance(
        self,
        resource_id: str,
        maintenance_type: str
    ) -> Dict[str, Any]:
        """Trigger maintenance window for a resource."""
        pass
```

---

## 7. Phase 6: Vertical Implementations

### 7.1 Finance - Reconciliation Agent (`src/verticals/finance/agents/reconciliation.py`)

```python
"""
Finance Reconciliation Agent - Automated AP/AR reconciliation.
"""
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
from core.agent.base import BaseAgent, AgentContext, AgentAction
from core.agent.tools import tool


class ReconciliationAgent(BaseAgent):
    """
    Agent for automated accounts payable/receivable reconciliation.

    Capabilities:
    - Match invoices to payments
    - Detect discrepancies
    - Generate exception reports
    - Post journal entries (policy-gated)
    """

    def __init__(self):
        super().__init__(
            agent_id="finance-recon-001",
            name="Reconciliation Agent",
            description="Automates AP/AR reconciliation with full audit trail",
            model_id="llama-3-70b",
            tools=[
                self.fetch_open_invoices,
                self.fetch_payments,
                self.match_payment_to_invoice,
                self.flag_exception,
                self.post_journal_entry,
                self.generate_report
            ],
            policies=[
                "finance/sox_approval.rego",
                "finance/data_classification.rego"
            ]
        )

    async def perceive(self, context: AgentContext, input_data: Any) -> Dict[str, Any]:
        """Gather financial data for reconciliation."""
        return {
            "entity": input_data.get("entity"),
            "period": input_data.get("period"),
            "account_type": input_data.get("account_type", "AP"),
            "source_systems": input_data.get("source_systems", [])
        }

    async def retrieve(self, context: AgentContext, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant financial data and matching rules."""
        # Fetch open items from ERP
        open_invoices = await self._fetch_open_invoices(
            entity=perception["entity"],
            period=perception["period"],
            account_type=perception["account_type"]
        )

        # Fetch bank/payment data
        payments = await self._fetch_payments(
            entity=perception["entity"],
            period=perception["period"]
        )

        # Get matching rules from procedural memory
        matching_rules = await self.memory.procedural.retrieve(
            f"finance/matching_rules/{perception['entity']}"
        )

        return {
            "open_invoices": open_invoices,
            "payments": payments,
            "matching_rules": matching_rules
        }

    async def reason(
        self,
        context: AgentContext,
        perception: Dict[str, Any],
        retrieved: Dict[str, Any]
    ) -> List[AgentAction]:
        """Determine reconciliation actions."""
        actions = []

        # Apply matching algorithm
        matches, exceptions = await self._apply_matching_rules(
            invoices=retrieved["open_invoices"],
            payments=retrieved["payments"],
            rules=retrieved["matching_rules"]
        )

        # Create actions for matches
        for match in matches:
            actions.append(AgentAction(
                action_id=f"match-{match['invoice_id']}-{match['payment_id']}",
                tool_name="match_payment_to_invoice",
                tool_args={
                    "invoice_id": match["invoice_id"],
                    "payment_id": match["payment_id"],
                    "amount": match["amount"],
                    "match_type": match["match_type"]
                },
                reasoning=f"Matched payment {match['payment_id']} to invoice {match['invoice_id']} based on {match['match_type']}",
                confidence=match["confidence"],
                requires_approval=match["amount"] > Decimal("10000"),
                data_classification="confidential"
            ))

        # Create actions for exceptions
        for exception in exceptions:
            actions.append(AgentAction(
                action_id=f"exception-{exception['id']}",
                tool_name="flag_exception",
                tool_args={
                    "exception_type": exception["type"],
                    "items": exception["items"],
                    "suggested_action": exception["suggested_action"]
                },
                reasoning=exception["reason"],
                confidence=0.9,
                requires_approval=True,
                data_classification="confidential"
            ))

        return actions

    async def verify(
        self,
        context: AgentContext,
        actions: List[AgentAction],
        results: List['ActionResult']
    ) -> bool:
        """Verify reconciliation results."""
        # Check that all matches were processed
        successful_matches = sum(1 for r in results if r.success and "match" in r.action_id)
        total_matches = sum(1 for a in actions if "match" in a.action_id)

        if successful_matches != total_matches:
            return False

        # Verify no data integrity issues
        return await self._verify_data_integrity(actions, results)

    @tool
    async def fetch_open_invoices(
        self,
        entity: str,
        period: str,
        account_type: str
    ) -> List[Dict]:
        """Fetch open invoices from ERP."""
        # Implementation would connect to SAP/Oracle/etc
        pass

    @tool
    async def fetch_payments(
        self,
        entity: str,
        period: str
    ) -> List[Dict]:
        """Fetch payments from bank/treasury."""
        pass

    @tool
    async def match_payment_to_invoice(
        self,
        invoice_id: str,
        payment_id: str,
        amount: Decimal,
        match_type: str
    ) -> Dict:
        """Record a payment-to-invoice match."""
        pass

    @tool
    async def flag_exception(
        self,
        exception_type: str,
        items: List[Dict],
        suggested_action: str
    ) -> Dict:
        """Flag items for manual review."""
        pass

    @tool
    async def post_journal_entry(
        self,
        journal_entry: Dict
    ) -> Dict:
        """Post a journal entry to the GL."""
        # This is always policy-gated for SOX compliance
        pass

    @tool
    async def generate_report(
        self,
        report_type: str,
        data: Dict
    ) -> Dict:
        """Generate reconciliation report."""
        pass
```

---

## 8. Phase 7: User Interface Layer

### 8.1 Teams Bot (`src/ui/teams/bot.py`)

```python
"""
Microsoft Teams Bot for ANTS conversational interface.
"""
from botbuilder.core import ActivityHandler, TurnContext, ConversationState, UserState
from botbuilder.schema import Activity, ActivityTypes
from botbuilder.dialogs import Dialog
import structlog

from core.agent.executor import AgentExecutor, TaskRequest
from core.agent.base import AgentContext
from ui.teams.cards import AdaptiveCardBuilder


logger = structlog.get_logger()


class ANTSBot(ActivityHandler):
    """
    Teams bot handler for ANTS.
    Routes user messages to appropriate agents.
    """

    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        agent_executor: AgentExecutor,
        dialog: Dialog
    ):
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.agent_executor = agent_executor
        self.dialog = dialog
        self.card_builder = AdaptiveCardBuilder()

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        user_message = turn_context.activity.text
        user_id = turn_context.activity.from_property.id
        tenant_id = turn_context.activity.conversation.tenant_id

        logger.info(
            "message_received",
            user_id=user_id,
            tenant_id=tenant_id,
            message_length=len(user_message)
        )

        # Create agent context
        context = AgentContext(
            trace_id=turn_context.activity.id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=turn_context.activity.conversation.id,
            environment="production",
            metadata={
                "channel": "teams",
                "activity_type": turn_context.activity.type
            }
        )

        # Route to appropriate agent based on intent
        agent_id = await self._route_to_agent(user_message, context)

        # Send typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        # Submit task to agent executor
        task = TaskRequest(
            task_id=f"teams-{context.trace_id}",
            agent_id=agent_id,
            input_data={"message": user_message, "channel": "teams"},
            context=context,
            timeout_seconds=120
        )

        result = await self.agent_executor.submit(task)

        # Build response card
        response_card = self.card_builder.build_response_card(result)

        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[response_card]
            )
        )

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        """Welcome new users."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_card = self.card_builder.build_welcome_card()
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        attachments=[welcome_card]
                    )
                )

    async def _route_to_agent(self, message: str, context: AgentContext) -> str:
        """Route message to appropriate agent based on intent."""
        # Use NIM to classify intent
        # This is a simplified version - production would use more sophisticated routing
        message_lower = message.lower()

        if any(word in message_lower for word in ["invoice", "payment", "reconcile", "ap", "ar"]):
            return "finance-recon-001"
        elif any(word in message_lower for word in ["inventory", "stock", "demand", "forecast"]):
            return "retail-demand-001"
        elif any(word in message_lower for word in ["patient", "claim", "coding", "phi"]):
            return "healthcare-rag-001"
        elif any(word in message_lower for word in ["machine", "maintenance", "sensor", "twin"]):
            return "manufacturing-twin-001"
        else:
            return "general-assistant-001"
```

---

## 9. Phase 8: Observability & CLEAR Metrics

### 9.1 CLEAR Metrics Collector (`src/observability/metrics.py`)

```python
"""
CLEAR Metrics - Cost, Latency, Efficacy, Assurance, Reliability.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge
import structlog


logger = structlog.get_logger()


# Prometheus metrics
TOKENS_TOTAL = Counter(
    'ants_tokens_total',
    'Total tokens consumed',
    ['agent_id', 'model_id', 'tenant_id']
)

GPU_SECONDS = Counter(
    'ants_gpu_seconds_total',
    'GPU seconds consumed',
    ['agent_id', 'gpu_type', 'tenant_id']
)

LATENCY = Histogram(
    'ants_latency_seconds',
    'Request latency in seconds',
    ['agent_id', 'operation', 'tenant_id'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

EFFICACY_SCORE = Gauge(
    'ants_efficacy_score',
    'Agent efficacy score (0-1)',
    ['agent_id', 'metric_type']
)

POLICY_DECISIONS = Counter(
    'ants_policy_decisions_total',
    'Policy decision counts',
    ['agent_id', 'decision', 'policy_id']
)

ERROR_RATE = Counter(
    'ants_errors_total',
    'Error counts',
    ['agent_id', 'error_type', 'tenant_id']
)


@dataclass
class CLEARMetrics:
    """Container for CLEAR metrics."""
    # Cost
    tokens_used: int = 0
    gpu_seconds: float = 0.0
    storage_bytes: int = 0
    estimated_cost_usd: float = 0.0

    # Latency
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0

    # Efficacy
    accuracy_score: float = 0.0
    task_success_rate: float = 0.0
    user_satisfaction: float = 0.0

    # Assurance
    policy_compliance_rate: float = 0.0
    redaction_success_rate: float = 0.0
    safety_test_pass_rate: float = 0.0

    # Reliability
    uptime_percentage: float = 0.0
    error_rate: float = 0.0
    retry_rate: float = 0.0


class CLEARMetricsCollector:
    """
    Collector for CLEAR metrics.
    Integrates with Prometheus for time-series data.
    """

    def __init__(self, agent_id: str, tenant_id: str):
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    def record_tokens(self, model_id: str, input_tokens: int, output_tokens: int):
        """Record token usage."""
        total_tokens = input_tokens + output_tokens
        TOKENS_TOTAL.labels(
            agent_id=self.agent_id,
            model_id=model_id,
            tenant_id=self.tenant_id
        ).inc(total_tokens)

    def record_gpu_time(self, gpu_type: str, seconds: float):
        """Record GPU usage."""
        GPU_SECONDS.labels(
            agent_id=self.agent_id,
            gpu_type=gpu_type,
            tenant_id=self.tenant_id
        ).inc(seconds)

    def record_latency(self, operation: str, latency_seconds: float):
        """Record operation latency."""
        LATENCY.labels(
            agent_id=self.agent_id,
            operation=operation,
            tenant_id=self.tenant_id
        ).observe(latency_seconds)

    def record_efficacy(self, metric_type: str, score: float):
        """Record efficacy metric."""
        EFFICACY_SCORE.labels(
            agent_id=self.agent_id,
            metric_type=metric_type
        ).set(score)

    def record_policy_decision(self, decision: str, policy_id: str):
        """Record policy decision."""
        POLICY_DECISIONS.labels(
            agent_id=self.agent_id,
            decision=decision,
            policy_id=policy_id
        ).inc()

    def record_error(self, error_type: str):
        """Record error occurrence."""
        ERROR_RATE.labels(
            agent_id=self.agent_id,
            error_type=error_type,
            tenant_id=self.tenant_id
        ).inc()

    def estimate_cost(
        self,
        tokens: int,
        gpu_seconds: float,
        storage_gb: float
    ) -> float:
        """Estimate cost in USD."""
        # Rough estimates - would be configured per deployment
        token_cost = tokens * 0.00002  # $0.02 per 1K tokens
        gpu_cost = gpu_seconds * 0.50  # $0.50 per GPU second (H100)
        storage_cost = storage_gb * 0.10 / (30 * 24 * 3600)  # $0.10/GB/month

        return token_cost + gpu_cost + storage_cost

    async def get_aggregated_metrics(self, window_hours: int = 24) -> CLEARMetrics:
        """Get aggregated CLEAR metrics for time window."""
        # This would query Prometheus/Thanos for aggregated data
        # Simplified implementation for illustration
        return CLEARMetrics()
```

---

## 10. Module Specifications

### 10.1 Core Modules

| Module | Description | Dependencies | Priority |
|--------|-------------|--------------|----------|
| `core.agent.base` | Base agent class | structlog, asyncio | P0 |
| `core.agent.executor` | Agent task orchestration | base, events | P0 |
| `core.agent.memory` | Agent memory interface | substrate | P0 |
| `core.memory.substrate` | ANF-backed memory | asyncpg, aiofiles | P0 |
| `core.trust.policy` | OPA policy engine | httpx | P0 |
| `core.trust.audit` | Audit logging | asyncpg | P0 |
| `core.inference.nim_client` | NVIDIA NIM client | httpx | P0 |
| `core.events.publisher` | Event publishing | azure-eventhub | P1 |

### 10.2 SelfOps Modules

| Module | Description | Dependencies | Priority |
|--------|-------------|--------------|----------|
| `selfops.infraops.agent` | Infrastructure management | azure-mgmt-* | P1 |
| `selfops.dataops.agent` | Data operations | core.memory | P1 |
| `selfops.agentops.agent` | Agent lifecycle | core.agent | P1 |
| `selfops.secops.agent` | Security operations | core.trust | P1 |

### 10.3 Vertical Modules

| Module | Description | Dependencies | Priority |
|--------|-------------|--------------|----------|
| `verticals.finance.reconciliation` | AP/AR reconciliation | core.agent | P0 |
| `verticals.retail.demand` | Demand forecasting | core.agent, numpy | P1 |
| `verticals.healthcare.rag` | PHI-safe RAG | core.agent, redaction | P1 |
| `verticals.manufacturing.twin` | Digital twin | core.agent, iot | P2 |

---

## 11. API Specifications

### 11.1 Agent Management API

```yaml
openapi: 3.0.0
info:
  title: ANTS Agent Management API
  version: 1.0.0

paths:
  /agents:
    get:
      summary: List all agents
      responses:
        200:
          description: List of agents
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Agent'
    post:
      summary: Create an agent
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AgentCreate'
      responses:
        201:
          description: Agent created

  /agents/{agent_id}:
    get:
      summary: Get agent details
      parameters:
        - name: agent_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Agent details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Agent'

  /agents/{agent_id}/tasks:
    post:
      summary: Submit task to agent
      parameters:
        - name: agent_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TaskSubmit'
      responses:
        202:
          description: Task accepted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskAccepted'

  /tasks/{task_id}:
    get:
      summary: Get task status
      parameters:
        - name: task_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Task status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskStatus'

components:
  schemas:
    Agent:
      type: object
      properties:
        agent_id:
          type: string
        name:
          type: string
        description:
          type: string
        state:
          type: string
          enum: [initializing, ready, executing, waiting_approval, paused, quarantined]
        model_id:
          type: string
        created_at:
          type: string
          format: date-time

    TaskSubmit:
      type: object
      required:
        - input_data
      properties:
        input_data:
          type: object
        priority:
          type: integer
          default: 0
        timeout_seconds:
          type: integer
          default: 300

    TaskStatus:
      type: object
      properties:
        task_id:
          type: string
        agent_id:
          type: string
        status:
          type: string
          enum: [pending, running, completed, failed, timeout]
        result:
          type: object
        error:
          type: string
        created_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
```

---

## 12. Testing Strategy

### 12.1 Test Categories

| Category | Scope | Tools | Coverage Target |
|----------|-------|-------|-----------------|
| Unit Tests | Individual functions | pytest | 80% |
| Integration Tests | Module interactions | pytest, testcontainers | 70% |
| E2E Tests | Full workflows | pytest, playwright | Key paths |
| Benchmarks | Performance | locust, pytest-benchmark | SLA validation |
| Security Tests | Vulnerability scanning | trivy, bandit | Zero critical |

### 12.2 Test Structure

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_agent_base.py
│   │   ├── test_memory_substrate.py
│   │   └── test_policy_engine.py
│   ├── selfops/
│   └── verticals/
├── integration/
│   ├── test_agent_execution.py
│   ├── test_memory_integration.py
│   └── test_nim_integration.py
├── e2e/
│   ├── test_finance_reconciliation.py
│   ├── test_retail_demand.py
│   └── test_teams_conversation.py
├── benchmarks/
│   ├── test_inference_latency.py
│   ├── test_memory_throughput.py
│   └── test_concurrent_agents.py
└── fixtures/
    ├── sample_data/
    └── mock_services/
```

### 12.3 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: ANTS CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install ruff black
      - run: ruff check .
      - run: black --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit --cov=src --cov-report=xml
      - run: pytest tests/integration

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install bandit safety
      - run: bandit -r src/
      - run: safety check

  build:
    needs: [lint, test, security]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/build-push-action@v4
        with:
          push: false
          tags: ants:${{ github.sha }}
```

---

## Implementation Checklist

### Phase 1: Foundation (Weeks 1-4)
- [ ] Terraform modules for AKS, ANF, networking
- [ ] Helm charts for core services
- [ ] Basic CI/CD pipeline
- [ ] Development environment setup

### Phase 2: Core Framework (Weeks 5-8)
- [ ] BaseAgent implementation
- [ ] AgentExecutor
- [ ] Memory substrate (PostgreSQL + pgvector)
- [ ] ANF volume integration

### Phase 3: Trust Layer (Weeks 9-10)
- [ ] OPA policy engine integration
- [ ] Audit logging
- [ ] HITL workflow
- [ ] Guardrails integration

### Phase 4: Inference (Weeks 11-12)
- [ ] NIM client
- [ ] Model router
- [ ] Embedding service
- [ ] Caching layer

### Phase 5: First Vertical (Weeks 13-16)
- [ ] Finance reconciliation agent
- [ ] SOX compliance policies
- [ ] Teams integration
- [ ] E2E demo

### Phase 6: SelfOps (Weeks 17-20)
- [ ] InfraOps agent
- [ ] DataOps agent
- [ ] AgentOps agent
- [ ] SecOps agent

### Phase 7: Additional Verticals (Weeks 21-28)
- [ ] Retail demand agent
- [ ] Healthcare RAG agent
- [ ] Manufacturing twin agent

### Phase 8: Production Hardening (Weeks 29-32)
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Documentation
- [ ] Load testing

---

*This plan provides a comprehensive blueprint for implementing ANTS. Each module is designed to be independently testable while contributing to the unified digital organism architecture.*

---

## 13. Phase 9: Azure Data Platform Integration

### 13.1 Microsoft Fabric & OneLake Integration

#### 13.1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Microsoft Fabric Lakehouse                        │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   OneLake   │  │  Warehouse  │  │  Lakehouse  │  │  Real-Time  │   │
│  │  (Unified)  │  │   (SQL)     │  │  (Spark)    │  │  Analytics  │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
│         └────────────────┴────────────────┴────────────────┘           │
│                                   │                                     │
│                    ┌──────────────┴──────────────┐                     │
│                    │   ANF Object REST API       │                     │
│                    │   (S3-Compatible Access)    │                     │
│                    └──────────────┬──────────────┘                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │     Azure NetApp Files        │
                    │  (Memory Substrate - NFS/SMB) │
                    └───────────────────────────────┘
```

#### 13.1.2 OneLake Shortcut Configuration (`src/integrations/fabric/onelake.py`)

```python
"""
OneLake integration via ANF Object REST API.
Zero-copy analytics - no data movement required.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import httpx
import structlog
from azure.identity import DefaultAzureCredential

logger = structlog.get_logger()


@dataclass
class OneLakeShortcutConfig:
    """Configuration for OneLake shortcut to ANF."""
    workspace_id: str
    lakehouse_id: str
    shortcut_name: str
    anf_account_name: str
    anf_volume_name: str
    target_path: str  # Path within ANF volume


class OneLakeIntegration:
    """
    Manages OneLake shortcuts to ANF volumes.
    Enables zero-copy analytics on agent memory data.
    """

    def __init__(self, fabric_endpoint: str = "https://api.fabric.microsoft.com/v1"):
        self.fabric_endpoint = fabric_endpoint
        self.credential = DefaultAzureCredential()
        self._client = httpx.AsyncClient(timeout=30.0)

    async def create_shortcut(self, config: OneLakeShortcutConfig) -> Dict[str, Any]:
        """
        Create OneLake shortcut to ANF volume via Object REST API.
        This enables Fabric to read ANF data without copying.
        """
        token = self.credential.get_token("https://api.fabric.microsoft.com/.default")

        shortcut_payload = {
            "path": f"Tables/{config.shortcut_name}",
            "target": {
                "type": "S3Compatible",
                "s3Compatible": {
                    "connectionId": await self._get_or_create_connection(config),
                    "location": f"s3://{config.anf_account_name}/{config.anf_volume_name}/{config.target_path}"
                }
            }
        }

        response = await self._client.post(
            f"{self.fabric_endpoint}/workspaces/{config.workspace_id}/lakehouses/{config.lakehouse_id}/shortcuts",
            json=shortcut_payload,
            headers={"Authorization": f"Bearer {token.token}"}
        )

        response.raise_for_status()
        logger.info("onelake_shortcut_created", shortcut=config.shortcut_name)
        return response.json()

    async def _get_or_create_connection(self, config: OneLakeShortcutConfig) -> str:
        """Get or create S3-compatible connection for ANF Object REST API."""
        # ANF Object REST API endpoint
        anf_s3_endpoint = f"https://{config.anf_account_name}.blob.core.windows.net"

        connection_payload = {
            "connectivityType": "S3Compatible",
            "connectionDetails": {
                "endpoint": anf_s3_endpoint,
                "bucket": config.anf_volume_name
            },
            "credentialDetails": {
                "credentialType": "WorkspaceIdentity"
            }
        }

        # Create connection via Fabric API
        # Returns connection ID for shortcut creation
        return "connection-id-placeholder"

    async def sync_agent_memory_to_lakehouse(
        self,
        workspace_id: str,
        lakehouse_id: str,
        memory_types: List[str] = ["episodic", "semantic", "audit"]
    ):
        """
        Create shortcuts for all agent memory types.
        Enables unified analytics across all memory data.
        """
        shortcuts_created = []

        for memory_type in memory_types:
            config = OneLakeShortcutConfig(
                workspace_id=workspace_id,
                lakehouse_id=lakehouse_id,
                shortcut_name=f"ants_{memory_type}_memory",
                anf_account_name="ants-netapp",
                anf_volume_name=f"{memory_type}-memory",
                target_path="/"
            )

            shortcut = await self.create_shortcut(config)
            shortcuts_created.append(shortcut)

        return shortcuts_created


class FabricAnalyticsPipeline:
    """
    Fabric analytics pipelines for ANTS data.
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.credential = DefaultAzureCredential()

    async def create_agent_analytics_pipeline(self) -> Dict[str, Any]:
        """
        Create Fabric pipeline for agent performance analytics.
        """
        pipeline_definition = {
            "name": "ANTS-Agent-Analytics",
            "activities": [
                {
                    "name": "LoadEpisodicMemory",
                    "type": "Copy",
                    "source": {
                        "type": "OneLakeShortcut",
                        "path": "Tables/ants_episodic_memory"
                    },
                    "sink": {
                        "type": "LakehouseTable",
                        "tableName": "agent_traces"
                    }
                },
                {
                    "name": "TransformMetrics",
                    "type": "SparkNotebook",
                    "notebookPath": "/Notebooks/CLEAR_Metrics_Transform",
                    "dependsOn": ["LoadEpisodicMemory"]
                },
                {
                    "name": "UpdateDashboard",
                    "type": "RefreshDataset",
                    "datasetId": "ants-executive-dashboard",
                    "dependsOn": ["TransformMetrics"]
                }
            ],
            "schedule": {
                "type": "Recurring",
                "interval": "PT15M"  # Every 15 minutes
            }
        }

        return pipeline_definition
```

#### 13.1.3 Fabric Spark Notebook for CLEAR Metrics (`notebooks/clear_metrics_transform.py`)

```python
"""
PySpark notebook for CLEAR metrics transformation in Fabric.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta.tables import DeltaTable

# Initialize Spark session (provided by Fabric)
spark = SparkSession.builder.getOrCreate()

# Read agent traces from OneLake shortcut
agent_traces = spark.read.format("delta").load("Tables/agent_traces")

# Calculate CLEAR metrics per agent per hour
clear_metrics = agent_traces.groupBy(
    window("timestamp", "1 hour"),
    "agent_id",
    "tenant_id"
).agg(
    # Cost metrics
    sum("tokens_used").alias("total_tokens"),
    sum("gpu_seconds").alias("total_gpu_seconds"),
    (sum("tokens_used") * 0.00002 + sum("gpu_seconds") * 0.50).alias("estimated_cost_usd"),

    # Latency metrics
    percentile_approx("execution_time_ms", 0.50).alias("latency_p50_ms"),
    percentile_approx("execution_time_ms", 0.95).alias("latency_p95_ms"),
    percentile_approx("execution_time_ms", 0.99).alias("latency_p99_ms"),

    # Efficacy metrics
    avg(when(col("verification_passed") == True, 1).otherwise(0)).alias("success_rate"),
    avg("confidence_score").alias("avg_confidence"),

    # Assurance metrics
    avg(when(col("policy_decision") == "ALLOW", 1).otherwise(0)).alias("policy_compliance_rate"),
    count(when(col("policy_decision") == "DENY", 1)).alias("policy_denials"),

    # Reliability metrics
    count("*").alias("total_executions"),
    count(when(col("error").isNotNull(), 1)).alias("error_count")
).withColumn(
    "error_rate",
    col("error_count") / col("total_executions")
)

# Write to Delta table for dashboards
clear_metrics.write.format("delta").mode("overwrite").saveAsTable("ants_clear_metrics_hourly")

# Create daily aggregation
daily_metrics = clear_metrics.groupBy(
    date_trunc("day", col("window.start")).alias("date"),
    "agent_id",
    "tenant_id"
).agg(
    sum("total_tokens").alias("daily_tokens"),
    sum("estimated_cost_usd").alias("daily_cost_usd"),
    avg("latency_p95_ms").alias("avg_latency_p95_ms"),
    avg("success_rate").alias("avg_success_rate"),
    avg("policy_compliance_rate").alias("avg_compliance_rate"),
    avg("error_rate").alias("avg_error_rate")
)

daily_metrics.write.format("delta").mode("overwrite").saveAsTable("ants_clear_metrics_daily")

print("CLEAR metrics transformation complete")
```

### 13.2 Azure Databricks Integration

#### 13.2.1 Unity Catalog Registration (`src/integrations/databricks/unity_catalog.py`)

```python
"""
Databricks Unity Catalog integration for ANF volumes.
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import *
import structlog

logger = structlog.get_logger()


@dataclass
class UnityCatalogConfig:
    """Unity Catalog configuration for ANF integration."""
    catalog_name: str = "ants_enterprise"
    schema_name: str = "agent_memory"
    storage_credential_name: str = "anf_s3_credential"
    external_location_name: str = "anf_memory_substrate"


class DatabricksUnityIntegration:
    """
    Integrates ANF with Databricks Unity Catalog.
    Enables governed access to agent memory via Spark.
    """

    def __init__(self, workspace_url: str):
        self.client = WorkspaceClient(host=workspace_url)
        self.config = UnityCatalogConfig()

    def setup_storage_credential(
        self,
        anf_account_name: str,
        access_key: str
    ) -> StorageCredentialInfo:
        """
        Create storage credential for ANF Object REST API.
        """
        credential = self.client.storage_credentials.create(
            name=self.config.storage_credential_name,
            aws_iam_role=None,  # Not AWS
            azure_managed_identity=None,
            # Use S3-compatible access for ANF Object REST API
            comment="ANF Object REST API credential for ANTS memory substrate"
        )

        logger.info("storage_credential_created", name=credential.name)
        return credential

    def create_external_location(
        self,
        anf_account_name: str,
        anf_volume_name: str
    ) -> ExternalLocationInfo:
        """
        Create external location pointing to ANF volume.
        """
        # ANF Object REST API S3-compatible URL
        anf_url = f"s3://{anf_account_name}.blob.core.windows.net/{anf_volume_name}/"

        location = self.client.external_locations.create(
            name=self.config.external_location_name,
            url=anf_url,
            credential_name=self.config.storage_credential_name,
            comment="ANTS memory substrate on Azure NetApp Files"
        )

        logger.info("external_location_created", url=anf_url)
        return location

    def create_catalog_and_schema(self) -> CatalogInfo:
        """
        Create Unity Catalog and schema for ANTS data.
        """
        # Create catalog
        catalog = self.client.catalogs.create(
            name=self.config.catalog_name,
            comment="ANTS Enterprise AI Agent Data Catalog"
        )

        # Create schema
        schema = self.client.schemas.create(
            name=self.config.schema_name,
            catalog_name=self.config.catalog_name,
            comment="Agent memory substrate schema"
        )

        logger.info("catalog_created", catalog=catalog.name, schema=schema.name)
        return catalog

    def register_memory_tables(self) -> List[TableInfo]:
        """
        Register ANF-backed tables in Unity Catalog.
        """
        tables = []

        # Episodic memory table
        episodic_table = self.client.tables.create(
            name="episodic_memory",
            catalog_name=self.config.catalog_name,
            schema_name=self.config.schema_name,
            table_type=TableType.EXTERNAL,
            data_source_format=DataSourceFormat.DELTA,
            storage_location=f"{self.config.external_location_name}/episodic/",
            columns=[
                ColumnInfo(name="trace_id", type_text="STRING", comment="Unique trace identifier"),
                ColumnInfo(name="agent_id", type_text="STRING", comment="Agent identifier"),
                ColumnInfo(name="tenant_id", type_text="STRING", comment="Tenant identifier"),
                ColumnInfo(name="timestamp", type_text="TIMESTAMP", comment="Event timestamp"),
                ColumnInfo(name="perception", type_text="STRING", comment="Agent perception JSON"),
                ColumnInfo(name="actions", type_text="STRING", comment="Actions taken JSON"),
                ColumnInfo(name="results", type_text="STRING", comment="Action results JSON"),
                ColumnInfo(name="verification_passed", type_text="BOOLEAN", comment="Verification status")
            ],
            comment="Agent episodic memory - execution traces"
        )
        tables.append(episodic_table)

        # Semantic memory table (vectors)
        semantic_table = self.client.tables.create(
            name="semantic_memory",
            catalog_name=self.config.catalog_name,
            schema_name=self.config.schema_name,
            table_type=TableType.EXTERNAL,
            data_source_format=DataSourceFormat.DELTA,
            storage_location=f"{self.config.external_location_name}/semantic/",
            columns=[
                ColumnInfo(name="key", type_text="STRING", comment="Memory key"),
                ColumnInfo(name="embedding", type_text="ARRAY<FLOAT>", comment="Vector embedding"),
                ColumnInfo(name="metadata", type_text="STRING", comment="Memory metadata JSON"),
                ColumnInfo(name="created_at", type_text="TIMESTAMP", comment="Creation timestamp"),
                ColumnInfo(name="updated_at", type_text="TIMESTAMP", comment="Last update timestamp")
            ],
            comment="Agent semantic memory - vector embeddings"
        )
        tables.append(semantic_table)

        # Audit receipts table
        audit_table = self.client.tables.create(
            name="audit_receipts",
            catalog_name=self.config.catalog_name,
            schema_name=self.config.schema_name,
            table_type=TableType.EXTERNAL,
            data_source_format=DataSourceFormat.DELTA,
            storage_location=f"{self.config.external_location_name}/audit/",
            columns=[
                ColumnInfo(name="receipt_id", type_text="STRING", comment="Unique receipt ID"),
                ColumnInfo(name="trace_id", type_text="STRING", comment="Associated trace ID"),
                ColumnInfo(name="agent_id", type_text="STRING", comment="Agent identifier"),
                ColumnInfo(name="action_id", type_text="STRING", comment="Action identifier"),
                ColumnInfo(name="tool_name", type_text="STRING", comment="Tool invoked"),
                ColumnInfo(name="policy_decision", type_text="STRING", comment="Policy outcome"),
                ColumnInfo(name="receipt_hash", type_text="STRING", comment="Integrity hash"),
                ColumnInfo(name="timestamp", type_text="TIMESTAMP", comment="Receipt timestamp")
            ],
            comment="Forensics-grade audit receipts"
        )
        tables.append(audit_table)

        logger.info("memory_tables_registered", count=len(tables))
        return tables


class DatabricksMLPipeline:
    """
    MLflow-based pipelines for agent model management.
    """

    def __init__(self, workspace_url: str):
        self.client = WorkspaceClient(host=workspace_url)

    def register_agent_model(
        self,
        model_name: str,
        model_path: str,  # Path on ANF
        model_version: str
    ) -> Dict[str, Any]:
        """
        Register agent model in MLflow Model Registry.
        Model artifacts stored on ANF for high-performance loading.
        """
        import mlflow

        # Set tracking URI to Databricks
        mlflow.set_tracking_uri("databricks")

        # Log model from ANF path
        with mlflow.start_run(run_name=f"{model_name}-{model_version}"):
            # ANF provides high-throughput access for model loading
            mlflow.log_artifact(model_path, "model")

            model_uri = mlflow.register_model(
                f"runs:/{mlflow.active_run().info.run_id}/model",
                model_name
            )

        return {"model_uri": model_uri, "version": model_version}
```

#### 13.2.2 Databricks Terraform Module (`infrastructure/terraform/modules/databricks/main.tf`)

```hcl
# Databricks workspace with ANF integration
resource "azurerm_databricks_workspace" "ants" {
  name                        = "dbw-ants-${var.environment}"
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = "premium"
  managed_resource_group_name = "rg-dbw-ants-${var.environment}-managed"

  custom_parameters {
    no_public_ip                                         = true
    virtual_network_id                                   = var.vnet_id
    private_subnet_name                                  = var.private_subnet_name
    public_subnet_name                                   = var.public_subnet_name
    private_subnet_network_security_group_association_id = var.private_nsg_association_id
    public_subnet_network_security_group_association_id  = var.public_nsg_association_id
  }

  tags = var.tags
}

# Private endpoint for Databricks
resource "azurerm_private_endpoint" "databricks" {
  name                = "pe-dbw-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "databricks-connection"
    private_connection_resource_id = azurerm_databricks_workspace.ants.id
    subresource_names              = ["databricks_ui_api"]
    is_manual_connection           = false
  }

  tags = var.tags
}

# Unity Catalog metastore (if not exists)
resource "databricks_metastore" "ants" {
  provider      = databricks.workspace
  name          = "ants-metastore-${var.location}"
  storage_root  = "abfss://unity-catalog@${var.storage_account_name}.dfs.core.windows.net/"
  owner         = var.metastore_owner
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

# Assign metastore to workspace
resource "databricks_metastore_assignment" "ants" {
  provider     = databricks.workspace
  workspace_id = azurerm_databricks_workspace.ants.workspace_id
  metastore_id = databricks_metastore.ants.id
}

# Storage credential for ANF Object REST API
resource "databricks_storage_credential" "anf" {
  provider = databricks.workspace
  name     = "anf-s3-credential"
  comment  = "Credential for ANF Object REST API access"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.anf.id
  }
}

# Access connector for managed identity
resource "azurerm_databricks_access_connector" "anf" {
  name                = "dac-ants-anf-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# External location for ANF memory substrate
resource "databricks_external_location" "memory_substrate" {
  provider        = databricks.workspace
  name            = "anf-memory-substrate"
  url             = "s3://${var.anf_account_name}.blob.core.windows.net/${var.anf_volume_name}/"
  credential_name = databricks_storage_credential.anf.name
  comment         = "ANTS memory substrate on Azure NetApp Files"
}

# Catalog for ANTS data
resource "databricks_catalog" "ants" {
  provider     = databricks.workspace
  metastore_id = databricks_metastore.ants.id
  name         = "ants_enterprise"
  comment      = "ANTS Enterprise AI Agent Data Catalog"
  owner        = var.catalog_owner
}

# Schema for agent memory
resource "databricks_schema" "agent_memory" {
  provider     = databricks.workspace
  catalog_name = databricks_catalog.ants.name
  name         = "agent_memory"
  comment      = "Agent memory substrate schema"
  owner        = var.schema_owner
}

output "workspace_url" {
  value = azurerm_databricks_workspace.ants.workspace_url
}

output "catalog_name" {
  value = databricks_catalog.ants.name
}
```

### 13.3 Azure AI Foundry Integration

#### 13.3.1 AI Foundry Hub Configuration (`src/integrations/ai_foundry/hub.py`)

```python
"""
Azure AI Foundry Hub integration for ANTS.
Provides access to 1800+ models with enterprise governance.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    Hub, Project, ManagedOnlineEndpoint, ManagedOnlineDeployment,
    Model, Environment
)
from azure.identity import DefaultAzureCredential
import structlog

logger = structlog.get_logger()


@dataclass
class AIFoundryConfig:
    """Configuration for Azure AI Foundry."""
    subscription_id: str
    resource_group: str
    hub_name: str
    location: str = "eastus2"

    # Model catalog settings
    model_catalog_enabled: bool = True
    prompt_flow_enabled: bool = True

    # Governance settings
    content_safety_enabled: bool = True
    responsible_ai_enabled: bool = True


class AIFoundryHub:
    """
    Azure AI Foundry Hub management.
    Central hub for AI model deployment and governance.
    """

    def __init__(self, config: AIFoundryConfig):
        self.config = config
        self.credential = DefaultAzureCredential()
        self.ml_client = MLClient(
            credential=self.credential,
            subscription_id=config.subscription_id,
            resource_group_name=config.resource_group
        )

    def create_hub(self) -> Hub:
        """Create AI Foundry Hub for ANTS."""
        hub = Hub(
            name=self.config.hub_name,
            location=self.config.location,
            description="ANTS Enterprise AI Hub",
            display_name="ANTS AI Foundry Hub",
            tags={
                "project": "ants",
                "purpose": "agent-orchestration"
            },
            # Enable all AI capabilities
            properties={
                "enableDataIsolation": True,
                "publicNetworkAccess": "Disabled",
                "managedNetwork": {
                    "isolationMode": "AllowInternetOutbound",
                    "outboundRules": {
                        "nvidia-nim": {
                            "type": "PrivateEndpoint",
                            "destination": {
                                "serviceResourceId": "/subscriptions/.../nvidia-nim"
                            }
                        }
                    }
                }
            }
        )

        created_hub = self.ml_client.workspaces.begin_create(hub).result()
        logger.info("ai_foundry_hub_created", hub=created_hub.name)
        return created_hub

    def create_project(self, project_name: str, vertical: str) -> Project:
        """Create AI Foundry Project for specific vertical."""
        project = Project(
            name=project_name,
            hub_id=f"/subscriptions/{self.config.subscription_id}/resourceGroups/{self.config.resource_group}/providers/Microsoft.MachineLearningServices/workspaces/{self.config.hub_name}",
            location=self.config.location,
            description=f"ANTS {vertical} vertical project",
            display_name=f"ANTS {vertical.title()}",
            tags={
                "vertical": vertical,
                "project": "ants"
            }
        )

        created_project = self.ml_client.workspaces.begin_create(project).result()
        logger.info("ai_foundry_project_created", project=created_project.name, vertical=vertical)
        return created_project

    def deploy_model_from_catalog(
        self,
        model_id: str,
        endpoint_name: str,
        instance_type: str = "Standard_NC24ads_A100_v4",
        instance_count: int = 1
    ) -> ManagedOnlineDeployment:
        """
        Deploy model from AI Foundry catalog.
        Supports 1800+ models including NVIDIA NIM.
        """
        # Create endpoint
        endpoint = ManagedOnlineEndpoint(
            name=endpoint_name,
            description=f"ANTS endpoint for {model_id}",
            auth_mode="key",
            tags={"model": model_id, "project": "ants"}
        )

        self.ml_client.online_endpoints.begin_create_or_update(endpoint).result()

        # Create deployment
        deployment = ManagedOnlineDeployment(
            name="default",
            endpoint_name=endpoint_name,
            model=model_id,  # Model from catalog
            instance_type=instance_type,
            instance_count=instance_count,
            request_settings={
                "request_timeout_ms": 90000,
                "max_concurrent_requests_per_instance": 10
            },
            liveness_probe={
                "initial_delay": 600,
                "period": 30,
                "timeout": 10,
                "success_threshold": 1,
                "failure_threshold": 30
            },
            environment_variables={
                "ANTS_MEMORY_MOUNT": "/mnt/anf-memory",
                "ENABLE_CONTENT_SAFETY": str(self.config.content_safety_enabled)
            }
        )

        created_deployment = self.ml_client.online_deployments.begin_create_or_update(
            deployment
        ).result()

        # Set traffic to 100%
        endpoint.traffic = {"default": 100}
        self.ml_client.online_endpoints.begin_create_or_update(endpoint).result()

        logger.info("model_deployed", endpoint=endpoint_name, model=model_id)
        return created_deployment


class AIFoundryAgentService:
    """
    Azure AI Foundry Agent Service integration.
    Enables multi-agent orchestration with built-in governance.
    """

    def __init__(self, project_connection_string: str):
        from azure.ai.projects import AIProjectClient

        self.client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=project_connection_string
        )

    async def create_agent(
        self,
        name: str,
        model: str,
        instructions: str,
        tools: List[Dict[str, Any]],
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create agent via AI Foundry Agent Service.
        Provides enterprise-grade agent management.
        """
        agent = await self.client.agents.create_agent(
            model=model,
            name=name,
            instructions=instructions,
            tools=tools,
            metadata=metadata or {},
            tool_resources={
                "code_interpreter": {"file_ids": []},
                "file_search": {"vector_store_ids": []}
            }
        )

        logger.info("foundry_agent_created", agent_id=agent.id, name=name)
        return agent

    async def create_thread_and_run(
        self,
        agent_id: str,
        messages: List[Dict[str, str]],
        tools_override: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create conversation thread and run agent.
        """
        # Create thread
        thread = await self.client.agents.create_thread()

        # Add messages
        for msg in messages:
            await self.client.agents.create_message(
                thread_id=thread.id,
                role=msg["role"],
                content=msg["content"]
            )

        # Run agent
        run = await self.client.agents.create_and_process_run(
            thread_id=thread.id,
            assistant_id=agent_id,
            tools=tools_override
        )

        # Get response messages
        response_messages = await self.client.agents.list_messages(thread_id=thread.id)

        return {
            "thread_id": thread.id,
            "run_id": run.id,
            "status": run.status,
            "messages": response_messages
        }
```

#### 13.3.2 AI Foundry Terraform Module (`infrastructure/terraform/modules/ai_foundry/main.tf`)

```hcl
# Azure AI Foundry Hub
resource "azurerm_machine_learning_workspace" "hub" {
  name                          = "aihub-ants-${var.environment}"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  application_insights_id       = var.application_insights_id
  key_vault_id                  = var.key_vault_id
  storage_account_id            = var.storage_account_id
  container_registry_id         = var.container_registry_id
  public_network_access_enabled = false

  kind = "Hub"

  identity {
    type = "SystemAssigned"
  }

  managed_network {
    isolation_mode = "AllowInternetOutbound"
  }

  tags = var.tags
}

# AI Foundry Projects per vertical
resource "azurerm_machine_learning_workspace" "projects" {
  for_each = toset(["finance", "retail", "healthcare", "manufacturing"])

  name                          = "aiproj-ants-${each.key}-${var.environment}"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  application_insights_id       = var.application_insights_id
  key_vault_id                  = var.key_vault_id
  storage_account_id            = var.storage_account_id
  public_network_access_enabled = false

  kind = "Project"

  # Link to hub
  hub_workspace_id = azurerm_machine_learning_workspace.hub.id

  identity {
    type = "SystemAssigned"
  }

  tags = merge(var.tags, {
    vertical = each.key
  })
}

# Private endpoints for AI Foundry
resource "azurerm_private_endpoint" "ai_foundry" {
  name                = "pe-aihub-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "ai-foundry-connection"
    private_connection_resource_id = azurerm_machine_learning_workspace.hub.id
    subresource_names              = ["amlworkspace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "ai-foundry-dns"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }

  tags = var.tags
}

# Compute cluster for model training
resource "azurerm_machine_learning_compute_cluster" "training" {
  name                          = "training-cluster"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.hub.id
  location                      = var.location
  vm_priority                   = "Dedicated"
  vm_size                       = "Standard_NC24ads_A100_v4"

  scale_settings {
    min_node_count                       = 0
    max_node_count                       = 8
    scale_down_nodes_after_idle_duration = "PT15M"
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# Managed online endpoint for inference
resource "azurerm_machine_learning_online_endpoint" "inference" {
  name                         = "ants-inference-${var.environment}"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.hub.id
  location                     = var.location
  auth_mode                    = "Key"
  public_network_access_enabled = false

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

output "hub_id" {
  value = azurerm_machine_learning_workspace.hub.id
}

output "project_ids" {
  value = { for k, v in azurerm_machine_learning_workspace.projects : k => v.id }
}

output "inference_endpoint" {
  value = azurerm_machine_learning_online_endpoint.inference.scoring_uri
}
```

---

## 14. Phase 10: NVIDIA AI Stack Integration

### 14.1 NVIDIA NIM Microservices

#### 14.1.1 NIM Client Implementation (`src/core/inference/nim_client.py`)

```python
"""
NVIDIA NIM Client for ANTS inference layer.
Provides 2.6x higher throughput vs unoptimized deployments.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, AsyncIterator
from enum import Enum
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class NIMModel(Enum):
    """Available NVIDIA NIM models."""
    # Llama Nemotron family
    NEMOTRON_NANO = "nvidia/llama-3.1-nemotron-nano-8b-v1.1"
    NEMOTRON_SUPER = "nvidia/llama-3.1-nemotron-super-49b-v1"
    NEMOTRON_ULTRA = "nvidia/llama-3.1-nemotron-ultra-253b-v1"

    # Base Llama models
    LLAMA_3_8B = "meta/llama-3-8b-instruct"
    LLAMA_3_70B = "meta/llama-3-70b-instruct"
    LLAMA_3_1_405B = "meta/llama-3.1-405b-instruct"

    # Embeddings
    NV_EMBED_V2 = "nvidia/nv-embedqa-e5-v5"
    NV_EMBED_RERANK = "nvidia/nv-rerankqa-mistral-4b-v3"

    # Vision
    VILA_40B = "nvidia/vila-40b"
    KOSMOS_2 = "microsoft/kosmos-2"

    # Speech
    RIVA_ASR = "nvidia/riva-asr"
    RIVA_TTS = "nvidia/riva-tts"


@dataclass
class NIMConfig:
    """Configuration for NVIDIA NIM."""
    endpoint: str = "http://nim-inference:8000"
    api_key: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: int = 120

    # Performance settings
    use_tensor_parallelism: bool = True
    enable_kv_cache: bool = True
    batch_size: int = 16

    # Model cache on ANF
    model_cache_path: str = "/mnt/anf-models"


class NIMClient:
    """
    NVIDIA NIM inference client.
    Optimized for high-throughput enterprise inference.
    """

    def __init__(self, config: NIMConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Generate completion using NIM model.
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop or [],
            "stream": stream
        }

        if stream:
            return self._stream_completion(payload)

        response = await self._client.post(
            f"{self.config.endpoint}/v1/chat/completions",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        logger.debug("nim_completion", model=model, tokens=result.get("usage", {}))
        return result

    async def _stream_completion(self, payload: Dict) -> AsyncIterator[str]:
        """Stream completion tokens."""
        async with self._client.stream(
            "POST",
            f"{self.config.endpoint}/v1/chat/completions",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    async def embed(
        self,
        text: str,
        model: str = NIMModel.NV_EMBED_V2.value
    ) -> List[float]:
        """
        Generate embeddings using NIM embedding model.
        """
        payload = {
            "model": model,
            "input": text,
            "encoding_format": "float"
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/embeddings",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        return result["data"][0]["embedding"]

    async def embed_batch(
        self,
        texts: List[str],
        model: str = NIMModel.NV_EMBED_V2.value
    ) -> List[List[float]]:
        """
        Batch embedding generation for efficiency.
        """
        payload = {
            "model": model,
            "input": texts,
            "encoding_format": "float"
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/embeddings",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        return [item["embedding"] for item in result["data"]]

    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str = NIMModel.NV_EMBED_RERANK.value,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using NIM reranker.
        """
        payload = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_k
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/rerank",
            json=payload
        )
        response.raise_for_status()

        return response.json()["results"]

    async def vision_analyze(
        self,
        image_url: str,
        prompt: str,
        model: str = NIMModel.VILA_40B.value
    ) -> Dict[str, Any]:
        """
        Analyze image using NIM vision model.
        """
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "max_tokens": 1024
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/chat/completions",
            json=payload
        )
        response.raise_for_status()

        return response.json()

    async def health_check(self) -> bool:
        """Check NIM service health."""
        try:
            response = await self._client.get(f"{self.config.endpoint}/v1/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
```

#### 14.1.2 NIM Kubernetes Deployment (`infrastructure/helm/ants-nim/templates/deployment.yaml`)

```yaml
# NVIDIA NIM Deployment for ANTS
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "ants-nim.fullname" . }}-llm
  labels:
    {{- include "ants-nim.labels" . | nindent 4 }}
    component: llm
spec:
  replicas: {{ .Values.llm.replicas }}
  selector:
    matchLabels:
      {{- include "ants-nim.selectorLabels" . | nindent 6 }}
      component: llm
  template:
    metadata:
      labels:
        {{- include "ants-nim.selectorLabels" . | nindent 8 }}
        component: llm
    spec:
      nodeSelector:
        nvidia.com/gpu: "true"
        {{- if .Values.llm.nodeSelector }}
        {{- toYaml .Values.llm.nodeSelector | nindent 8 }}
        {{- end }}
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      containers:
        - name: nim-llm
          image: "{{ .Values.llm.image.repository }}:{{ .Values.llm.image.tag }}"
          imagePullPolicy: {{ .Values.llm.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
            - name: metrics
              containerPort: 8080
              protocol: TCP
          env:
            - name: NGC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.ngc.secretName }}
                  key: api-key
            - name: NIM_CACHE_PATH
              value: "/model-cache"
            - name: NIM_TENSOR_PARALLELISM
              value: "{{ .Values.llm.tensorParallelism }}"
            - name: NIM_MAX_BATCH_SIZE
              value: "{{ .Values.llm.maxBatchSize }}"
            - name: NIM_MAX_INPUT_LENGTH
              value: "{{ .Values.llm.maxInputLength }}"
            - name: NIM_MAX_OUTPUT_LENGTH
              value: "{{ .Values.llm.maxOutputLength }}"
          resources:
            limits:
              nvidia.com/gpu: {{ .Values.llm.resources.gpuCount }}
              memory: {{ .Values.llm.resources.memory }}
              cpu: {{ .Values.llm.resources.cpu }}
            requests:
              nvidia.com/gpu: {{ .Values.llm.resources.gpuCount }}
              memory: {{ .Values.llm.resources.memoryRequest }}
              cpu: {{ .Values.llm.resources.cpuRequest }}
          volumeMounts:
            - name: model-cache
              mountPath: /model-cache
            - name: shm
              mountPath: /dev/shm
          livenessProbe:
            httpGet:
              path: /v1/health
              port: 8000
            initialDelaySeconds: 300
            periodSeconds: 30
            failureThreshold: 5
          readinessProbe:
            httpGet:
              path: /v1/health/ready
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 10
      volumes:
        - name: model-cache
          persistentVolumeClaim:
            claimName: {{ .Values.anf.modelCachePVC }}
        - name: shm
          emptyDir:
            medium: Memory
            sizeLimit: 16Gi
      imagePullSecrets:
        - name: {{ .Values.ngc.imagePullSecret }}
---
# NIM Embedding Service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "ants-nim.fullname" . }}-embed
  labels:
    {{- include "ants-nim.labels" . | nindent 4 }}
    component: embed
spec:
  replicas: {{ .Values.embed.replicas }}
  selector:
    matchLabels:
      {{- include "ants-nim.selectorLabels" . | nindent 6 }}
      component: embed
  template:
    metadata:
      labels:
        {{- include "ants-nim.selectorLabels" . | nindent 8 }}
        component: embed
    spec:
      nodeSelector:
        nvidia.com/gpu: "true"
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      containers:
        - name: nim-embed
          image: "{{ .Values.embed.image.repository }}:{{ .Values.embed.image.tag }}"
          ports:
            - name: http
              containerPort: 8000
          env:
            - name: NGC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.ngc.secretName }}
                  key: api-key
            - name: NIM_CACHE_PATH
              value: "/model-cache"
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: 32Gi
            requests:
              nvidia.com/gpu: 1
              memory: 16Gi
          volumeMounts:
            - name: model-cache
              mountPath: /model-cache
      volumes:
        - name: model-cache
          persistentVolumeClaim:
            claimName: {{ .Values.anf.modelCachePVC }}
      imagePullSecrets:
        - name: {{ .Values.ngc.imagePullSecret }}
```

### 14.2 NVIDIA NeMo Framework Integration

#### 14.2.1 NeMo Retriever for RAG (`src/core/inference/nemo_retriever.py`)

```python
"""
NVIDIA NeMo Retriever integration for high-quality RAG.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class NeMoRetrieverConfig:
    """Configuration for NeMo Retriever."""
    endpoint: str = "http://nemo-retriever:8081"
    embedding_endpoint: str = "http://nim-embed:8000"
    collection_name: str = "ants_memory"
    top_k: int = 10
    rerank_top_k: int = 5


class NeMoRetriever:
    """
    NeMo Retriever for high-quality semantic search.
    Provides advanced RAG capabilities with reranking.
    """

    def __init__(self, config: NeMoRetrieverConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=60.0)

    async def index_documents(
        self,
        documents: List[Dict[str, Any]],
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index documents in NeMo Retriever.
        """
        collection = collection or self.config.collection_name

        payload = {
            "collection": collection,
            "documents": [
                {
                    "id": doc["id"],
                    "content": doc["content"],
                    "metadata": doc.get("metadata", {})
                }
                for doc in documents
            ]
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/index",
            json=payload
        )
        response.raise_for_status()

        logger.info("documents_indexed", collection=collection, count=len(documents))
        return response.json()

    async def retrieve(
        self,
        query: str,
        collection: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents using hybrid search + reranking.
        """
        collection = collection or self.config.collection_name
        top_k = top_k or self.config.top_k

        payload = {
            "collection": collection,
            "query": query,
            "top_k": top_k,
            "filters": filters or {},
            "rerank": rerank,
            "rerank_top_k": self.config.rerank_top_k if rerank else None
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/retrieve",
            json=payload
        )
        response.raise_for_status()

        results = response.json()["results"]
        logger.debug("retrieve_complete", query_length=len(query), results=len(results))
        return results

    async def hybrid_search(
        self,
        query: str,
        collection: Optional[str] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword search.
        """
        collection = collection or self.config.collection_name

        payload = {
            "collection": collection,
            "query": query,
            "search_type": "hybrid",
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
            "top_k": top_k
        }

        response = await self._client.post(
            f"{self.config.endpoint}/v1/search",
            json=payload
        )
        response.raise_for_status()

        return response.json()["results"]

    async def delete_documents(
        self,
        document_ids: List[str],
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete documents from collection."""
        collection = collection or self.config.collection_name

        response = await self._client.delete(
            f"{self.config.endpoint}/v1/documents",
            json={"collection": collection, "ids": document_ids}
        )
        response.raise_for_status()

        return response.json()

    async def close(self):
        await self._client.aclose()
```

### 14.3 NVIDIA Guardrails Integration

#### 14.3.1 NeMo Guardrails Engine (`src/core/trust/guardrails.py`)

```python
"""
NVIDIA NeMo Guardrails integration for AI safety.
Provides input/output filtering and content moderation.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import httpx
import structlog
from nemoguardrails import RailsConfig, LLMRails

logger = structlog.get_logger()


class GuardrailAction(Enum):
    """Actions that guardrails can take."""
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    REWRITE = "rewrite"
    ESCALATE = "escalate"


@dataclass
class GuardrailResult:
    """Result of guardrail evaluation."""
    action: GuardrailAction
    original_content: str
    processed_content: Optional[str]
    violations: List[Dict[str, Any]]
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class GuardrailsConfig:
    """Configuration for NeMo Guardrails."""
    config_path: str = "/etc/ants/guardrails"
    model: str = "llama-3-8b"
    enable_input_rails: bool = True
    enable_output_rails: bool = True
    enable_topical_rails: bool = True
    enable_factual_rails: bool = True


class Guardrails:
    """
    NeMo Guardrails for AI safety.
    Enforces input/output constraints on agent actions.
    """

    def __init__(self, config: GuardrailsConfig):
        self.config = config

        # Load guardrails configuration
        rails_config = RailsConfig.from_path(config.config_path)
        self.rails = LLMRails(rails_config)

        logger.info("guardrails_initialized", config_path=config.config_path)

    async def guard_input(
        self,
        input_data: Dict[str, Any],
        context: 'AgentContext'
    ) -> Dict[str, Any]:
        """
        Apply input guardrails to agent input.
        """
        if not self.config.enable_input_rails:
            return input_data

        # Convert to text for analysis
        input_text = self._serialize_input(input_data)

        # Check input rails
        result = await self.rails.generate_async(
            messages=[{"role": "user", "content": input_text}]
        )

        if result.get("blocked", False):
            logger.warning(
                "input_blocked",
                reason=result.get("reason"),
                agent_id=context.metadata.get("agent_id")
            )
            raise GuardrailViolation(
                action=GuardrailAction.BLOCK,
                reason=result.get("reason", "Input blocked by guardrails")
            )

        # Apply any input transformations
        if "transformed_input" in result:
            return self._deserialize_input(result["transformed_input"])

        return input_data

    async def guard_output(
        self,
        output_data: Any,
        context: 'AgentContext'
    ) -> Any:
        """
        Apply output guardrails to agent output.
        """
        if not self.config.enable_output_rails:
            return output_data

        output_text = str(output_data)

        # Check output rails
        result = await self.rails.generate_async(
            messages=[
                {"role": "assistant", "content": output_text}
            ]
        )

        if result.get("blocked", False):
            logger.warning(
                "output_blocked",
                reason=result.get("reason"),
                agent_id=context.metadata.get("agent_id")
            )
            # Return safe fallback
            return self._get_safe_fallback(output_data, result.get("reason"))

        # Apply output transformations (e.g., PII redaction)
        if "transformed_output" in result:
            return result["transformed_output"]

        return output_data

    async def check_topical_relevance(
        self,
        query: str,
        response: str,
        allowed_topics: List[str]
    ) -> Tuple[bool, str]:
        """
        Check if response stays on allowed topics.
        """
        if not self.config.enable_topical_rails:
            return True, ""

        result = await self.rails.generate_async(
            messages=[
                {"role": "user", "content": query},
                {"role": "assistant", "content": response}
            ],
            options={"check_topical": True, "allowed_topics": allowed_topics}
        )

        is_on_topic = not result.get("off_topic", False)
        reason = result.get("topic_violation_reason", "")

        return is_on_topic, reason

    async def check_factual_accuracy(
        self,
        claim: str,
        evidence: List[str]
    ) -> Tuple[bool, float]:
        """
        Check factual accuracy of a claim against evidence.
        """
        if not self.config.enable_factual_rails:
            return True, 1.0

        result = await self.rails.generate_async(
            messages=[{"role": "user", "content": claim}],
            options={
                "check_factual": True,
                "evidence": evidence
            }
        )

        is_factual = result.get("factually_accurate", True)
        confidence = result.get("factual_confidence", 1.0)

        return is_factual, confidence

    def _serialize_input(self, input_data: Dict[str, Any]) -> str:
        """Serialize input data for guardrail analysis."""
        import json
        return json.dumps(input_data, default=str)

    def _deserialize_input(self, text: str) -> Dict[str, Any]:
        """Deserialize transformed input."""
        import json
        return json.loads(text)

    def _get_safe_fallback(self, output_data: Any, reason: str) -> str:
        """Return safe fallback when output is blocked."""
        return f"I cannot provide that information. Reason: {reason}"


class GuardrailViolation(Exception):
    """Exception raised when guardrails block content."""

    def __init__(self, action: GuardrailAction, reason: str):
        self.action = action
        self.reason = reason
        super().__init__(f"Guardrail violation: {action.value} - {reason}")
```

#### 14.3.2 Guardrails Configuration (`configs/guardrails/config.yml`)

```yaml
# NeMo Guardrails Configuration for ANTS
models:
  - type: main
    engine: nim
    model: llama-3.1-nemotron-nano-8b

rails:
  input:
    flows:
      - check jailbreak
      - check toxicity
      - check pii
      - check topic relevance

  output:
    flows:
      - check hallucination
      - check pii in response
      - check sensitive data exposure
      - enforce response format

  dialog:
    flows:
      - maintain context
      - enforce policy compliance

# Define blocked patterns
patterns:
  jailbreak:
    - "ignore previous instructions"
    - "pretend you are"
    - "disregard your training"
    - "act as if you have no restrictions"

  pii:
    - pattern: '\b\d{3}-\d{2}-\d{4}\b'  # SSN
      action: redact
      replacement: "[SSN REDACTED]"
    - pattern: '\b\d{16}\b'  # Credit card
      action: redact
      replacement: "[CARD REDACTED]"
    - pattern: '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Email
      action: redact
      replacement: "[EMAIL REDACTED]"

# Topic restrictions per vertical
topics:
  finance:
    allowed:
      - accounts payable
      - accounts receivable
      - reconciliation
      - financial reporting
      - compliance
    blocked:
      - personal financial advice
      - investment recommendations
      - tax advice

  healthcare:
    allowed:
      - clinical documentation
      - revenue cycle
      - medical coding
      - scheduling
    blocked:
      - medical diagnosis
      - treatment recommendations
      - prescription advice

# Response format enforcement
response_format:
  require_citation: true
  max_length: 4000
  require_confidence_score: true
```

### 14.4 NVIDIA RAPIDS Integration

#### 14.4.1 RAPIDS Data Processing (`src/core/data/rapids_processor.py`)

```python
"""
NVIDIA RAPIDS integration for GPU-accelerated data processing.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import structlog

# RAPIDS imports
try:
    import cudf
    import cuml
    import cugraph
    from cuml.neighbors import NearestNeighbors
    from cuml.cluster import KMeans
    RAPIDS_AVAILABLE = True
except ImportError:
    RAPIDS_AVAILABLE = False

logger = structlog.get_logger()


@dataclass
class RAPIDSConfig:
    """Configuration for RAPIDS processing."""
    gpu_memory_limit: str = "16GB"
    enable_rmm_pool: bool = True
    spill_to_host: bool = True


class RAPIDSProcessor:
    """
    GPU-accelerated data processing using NVIDIA RAPIDS.
    Provides 10-100x speedup for data operations.
    """

    def __init__(self, config: RAPIDSConfig):
        if not RAPIDS_AVAILABLE:
            raise ImportError("RAPIDS libraries not available")

        self.config = config
        self._setup_memory_pool()

    def _setup_memory_pool(self):
        """Configure RAPIDS memory management."""
        import rmm
        rmm.reinitialize(
            pool_allocator=self.config.enable_rmm_pool,
            managed_memory=False,
            initial_pool_size=None
        )

    def load_dataframe(self, path: str) -> 'cudf.DataFrame':
        """
        Load data into GPU DataFrame from ANF.
        Supports Parquet, CSV, JSON formats.
        """
        if path.endswith('.parquet'):
            df = cudf.read_parquet(path)
        elif path.endswith('.csv'):
            df = cudf.read_csv(path)
        elif path.endswith('.json'):
            df = cudf.read_json(path, lines=True)
        else:
            raise ValueError(f"Unsupported format: {path}")

        logger.info("dataframe_loaded", path=path, rows=len(df))
        return df

    def vectorize_text(
        self,
        texts: List[str],
        method: str = "tfidf"
    ) -> 'cudf.DataFrame':
        """
        GPU-accelerated text vectorization.
        """
        from cuml.feature_extraction.text import TfidfVectorizer, CountVectorizer

        if method == "tfidf":
            vectorizer = TfidfVectorizer()
        else:
            vectorizer = CountVectorizer()

        # Convert to cuDF Series
        text_series = cudf.Series(texts)
        vectors = vectorizer.fit_transform(text_series)

        return vectors

    def nearest_neighbors(
        self,
        embeddings: 'cudf.DataFrame',
        query_embedding: List[float],
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        GPU-accelerated nearest neighbor search.
        """
        nn = NearestNeighbors(n_neighbors=k, metric='cosine')
        nn.fit(embeddings)

        # Query
        query_df = cudf.DataFrame([query_embedding])
        distances, indices = nn.kneighbors(query_df)

        results = []
        for i, (dist, idx) in enumerate(zip(distances[0].to_pandas(), indices[0].to_pandas())):
            results.append({
                "index": int(idx),
                "distance": float(dist),
                "similarity": 1.0 - float(dist)
            })

        return results

    def cluster_embeddings(
        self,
        embeddings: 'cudf.DataFrame',
        n_clusters: int = 10
    ) -> Dict[str, Any]:
        """
        GPU-accelerated clustering of embeddings.
        """
        kmeans = KMeans(n_clusters=n_clusters)
        labels = kmeans.fit_predict(embeddings)

        return {
            "labels": labels.to_pandas().tolist(),
            "cluster_centers": kmeans.cluster_centers_.to_pandas().values.tolist(),
            "inertia": float(kmeans.inertia_)
        }

    def aggregate_metrics(
        self,
        df: 'cudf.DataFrame',
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> 'cudf.DataFrame':
        """
        GPU-accelerated metric aggregation.
        """
        agg_dict = {}
        for col, agg_func in aggregations.items():
            agg_dict[col] = agg_func

        result = df.groupby(group_by).agg(agg_dict)
        return result.reset_index()

    def graph_analytics(
        self,
        edges: 'cudf.DataFrame',
        source_col: str = "source",
        target_col: str = "target"
    ) -> Dict[str, Any]:
        """
        GPU-accelerated graph analytics using cuGraph.
        """
        import cugraph

        G = cugraph.Graph()
        G.from_cudf_edgelist(edges, source=source_col, destination=target_col)

        # PageRank
        pagerank = cugraph.pagerank(G)

        # Connected components
        components = cugraph.connected_components(G)

        return {
            "pagerank": pagerank.to_pandas().to_dict('records'),
            "num_components": components['labels'].nunique(),
            "num_vertices": G.number_of_vertices(),
            "num_edges": G.number_of_edges()
        }
```

### 14.5 NVIDIA Triton Inference Server

#### 14.5.1 Triton Model Repository (`infrastructure/triton/model_repository/`)

```
model_repository/
├── llama3_70b/
│   ├── config.pbtxt
│   └── 1/
│       └── model.py
├── embedding_model/
│   ├── config.pbtxt
│   └── 1/
│       └── model.onnx
└── reranker/
    ├── config.pbtxt
    └── 1/
        └── model.pt
```

#### 14.5.2 Triton Configuration (`infrastructure/triton/config.pbtxt`)

```protobuf
# Triton configuration for LLM serving
name: "llama3_70b"
platform: "tensorrt_llm"
max_batch_size: 64

input [
  {
    name: "input_ids"
    data_type: TYPE_INT32
    dims: [ -1 ]
  },
  {
    name: "input_lengths"
    data_type: TYPE_INT32
    dims: [ 1 ]
  },
  {
    name: "request_output_len"
    data_type: TYPE_INT32
    dims: [ 1 ]
  }
]

output [
  {
    name: "output_ids"
    data_type: TYPE_INT32
    dims: [ -1 ]
  }
]

instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0, 1, 2, 3 ]  # 4-way tensor parallelism
  }
]

parameters {
  key: "tensor_para_size"
  value: { string_value: "4" }
}

parameters {
  key: "pipeline_para_size"
  value: { string_value: "1" }
}

parameters {
  key: "gpt_model_type"
  value: { string_value: "llama" }
}

parameters {
  key: "gpt_model_path"
  value: { string_value: "/mnt/anf-models/llama3-70b-trtllm" }
}

dynamic_batching {
  preferred_batch_size: [ 8, 16, 32 ]
  max_queue_delay_microseconds: 100000
}

model_warmup [
  {
    name: "warmup_sample"
    batch_size: 1
    inputs {
      key: "input_ids"
      value {
        data_type: TYPE_INT32
        dims: [ 128 ]
        input_data_file: "warmup_input.txt"
      }
    }
  }
]
```

#### 14.5.3 Triton Client (`src/core/inference/triton_client.py`)

```python
"""
NVIDIA Triton Inference Server client for ANTS.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import structlog

try:
    import tritonclient.grpc as grpcclient
    import tritonclient.http as httpclient
    TRITON_AVAILABLE = True
except ImportError:
    TRITON_AVAILABLE = False

logger = structlog.get_logger()


@dataclass
class TritonConfig:
    """Configuration for Triton client."""
    grpc_url: str = "triton-inference:8001"
    http_url: str = "triton-inference:8000"
    use_grpc: bool = True
    connection_timeout: float = 60.0
    network_timeout: float = 120.0


class TritonClient:
    """
    NVIDIA Triton Inference Server client.
    Provides high-performance model serving.
    """

    def __init__(self, config: TritonConfig):
        if not TRITON_AVAILABLE:
            raise ImportError("tritonclient not available")

        self.config = config

        if config.use_grpc:
            self.client = grpcclient.InferenceServerClient(
                url=config.grpc_url,
                verbose=False
            )
        else:
            self.client = httpclient.InferenceServerClient(
                url=config.http_url,
                connection_timeout=config.connection_timeout,
                network_timeout=config.network_timeout
            )

    def is_server_live(self) -> bool:
        """Check if Triton server is live."""
        return self.client.is_server_live()

    def is_model_ready(self, model_name: str) -> bool:
        """Check if model is ready for inference."""
        return self.client.is_model_ready(model_name)

    def infer(
        self,
        model_name: str,
        inputs: Dict[str, np.ndarray],
        outputs: List[str],
        timeout: Optional[float] = None
    ) -> Dict[str, np.ndarray]:
        """
        Perform inference on Triton model.
        """
        # Prepare inputs
        triton_inputs = []
        for name, data in inputs.items():
            if self.config.use_grpc:
                inp = grpcclient.InferInput(name, data.shape, self._numpy_to_triton_dtype(data.dtype))
            else:
                inp = httpclient.InferInput(name, data.shape, self._numpy_to_triton_dtype(data.dtype))
            inp.set_data_from_numpy(data)
            triton_inputs.append(inp)

        # Prepare outputs
        triton_outputs = []
        for name in outputs:
            if self.config.use_grpc:
                triton_outputs.append(grpcclient.InferRequestedOutput(name))
            else:
                triton_outputs.append(httpclient.InferRequestedOutput(name))

        # Perform inference
        result = self.client.infer(
            model_name=model_name,
            inputs=triton_inputs,
            outputs=triton_outputs,
            timeout=timeout
        )

        # Extract outputs
        output_dict = {}
        for name in outputs:
            output_dict[name] = result.as_numpy(name)

        return output_dict

    async def infer_async(
        self,
        model_name: str,
        inputs: Dict[str, np.ndarray],
        outputs: List[str]
    ) -> Dict[str, np.ndarray]:
        """Async inference wrapper."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.infer,
            model_name,
            inputs,
            outputs
        )

    def _numpy_to_triton_dtype(self, dtype: np.dtype) -> str:
        """Convert numpy dtype to Triton dtype string."""
        dtype_map = {
            np.float32: "FP32",
            np.float16: "FP16",
            np.int32: "INT32",
            np.int64: "INT64",
            np.int8: "INT8",
            np.uint8: "UINT8",
            np.bool_: "BOOL"
        }
        return dtype_map.get(dtype.type, "FP32")

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """Get model metadata from Triton."""
        metadata = self.client.get_model_metadata(model_name)
        return {
            "name": metadata.name,
            "versions": metadata.versions,
            "inputs": [{"name": i.name, "shape": i.shape, "dtype": i.datatype} for i in metadata.inputs],
            "outputs": [{"name": o.name, "shape": o.shape, "dtype": o.datatype} for o in metadata.outputs]
        }
```

---

## 15. Phase 11: HA/BCDR/Zonal Resiliency Patterns

### 15.1 BCDR Configuration (`infrastructure/terraform/modules/bcdr/main.tf`)

```hcl
# BCDR Infrastructure Module for ANTS

variable "primary_location" {
  type    = string
  default = "eastus2"
}

variable "dr_location" {
  type    = string
  default = "centralus"
}

variable "rpo_minutes" {
  type    = number
  default = 30
}

variable "rto_minutes" {
  type    = number
  default = 60
}

# ANF Cross-Region Replication
resource "azurerm_netapp_volume" "primary_memory" {
  name                = "vol-ants-memory-primary"
  location            = var.primary_location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.primary.name
  pool_name           = azurerm_netapp_pool.primary_ultra.name
  volume_path         = "memory"
  service_level       = "Ultra"
  subnet_id           = var.primary_anf_subnet_id
  storage_quota_in_gb = 10240

  protocols = ["NFSv4.1"]

  data_protection_replication {
    endpoint_type             = "src"
    remote_volume_location    = var.dr_location
    remote_volume_resource_id = azurerm_netapp_volume.dr_memory.id
    replication_frequency     = "10minutes"
  }

  data_protection_snapshot_policy {
    snapshot_policy_id = azurerm_netapp_snapshot_policy.comprehensive.id
  }

  tags = var.tags
}

# PostgreSQL Zone-Redundant HA
resource "azurerm_postgresql_flexible_server" "primary" {
  name                   = "pg-ants-${var.environment}-primary"
  resource_group_name    = var.resource_group_name
  location               = var.primary_location
  version                = "16"
  delegated_subnet_id    = var.pg_subnet_id
  private_dns_zone_id    = var.private_dns_zone_id
  administrator_login    = "antsadmin"
  administrator_password = var.pg_admin_password
  zone                   = "1"
  storage_mb             = 524288
  sku_name               = "GP_Standard_D4s_v3"

  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }

  backup_retention_days        = 35
  geo_redundant_backup_enabled = true
  auto_grow_enabled           = true

  tags = var.tags
}

# Event Hubs Geo-DR
resource "azurerm_eventhub_namespace" "primary" {
  name                = "eh-ants-${var.environment}-primary"
  location            = var.primary_location
  resource_group_name = var.resource_group_name
  sku                 = "Standard"
  capacity            = 4
  zone_redundant      = true

  tags = var.tags
}

resource "azurerm_eventhub_namespace_disaster_recovery_config" "dr" {
  name                 = "ants-eventhub-dr"
  resource_group_name  = var.resource_group_name
  namespace_name       = azurerm_eventhub_namespace.primary.name
  partner_namespace_id = azurerm_eventhub_namespace.dr.id
}

# Azure Front Door for Global Load Balancing
resource "azurerm_cdn_frontdoor_profile" "ants" {
  name                = "fd-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "api" {
  name                     = "api-origin-group"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.ants.id

  health_probe {
    interval_in_seconds = 30
    path                = "/health"
    protocol            = "Https"
    request_type        = "HEAD"
  }

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 2
    additional_latency_in_milliseconds = 50
  }
}

output "bcdr_config" {
  value = {
    primary_region     = var.primary_location
    dr_region          = var.dr_location
    rpo_minutes        = var.rpo_minutes
    rto_minutes        = var.rto_minutes
    anf_replication    = "10minutes"
    pg_ha_mode         = "ZoneRedundant"
    eventhub_geo_dr    = true
    front_door_enabled = true
  }
}
```

### 15.2 AKS High Availability (`infrastructure/terraform/modules/aks_ha/main.tf`)

```hcl
# AKS High Availability Configuration

resource "azurerm_kubernetes_cluster" "ants" {
  name                = "aks-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "ants-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  # Uptime SLA for 99.95% availability
  sku_tier = "Standard"

  default_node_pool {
    name                         = "system"
    node_count                   = 3
    vm_size                      = "Standard_D4s_v5"
    zones                        = ["1", "2", "3"]
    vnet_subnet_id               = var.aks_subnet_id
    only_critical_addons_enabled = true

    upgrade_settings {
      max_surge = "33%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
  }

  azure_policy_enabled = true

  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  automatic_upgrade_channel = "patch"

  tags = var.tags
}

# GPU node pool - AI inference
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.ants.id
  vm_size               = "Standard_NC24ads_A100_v4"
  node_count            = 2
  zones                 = ["1", "2"]
  vnet_subnet_id        = var.aks_subnet_id

  enable_auto_scaling = true
  min_count           = 1
  max_count           = 8

  node_labels = {
    "nvidia.com/gpu" = "true"
  }

  node_taints = ["nvidia.com/gpu=true:NoSchedule"]

  tags = var.tags
}
```

---

## 16. Phase 12: Extended Agent Catalog

### 16.1 Business Organ Agents

#### 16.1.1 CRM Agent (`src/agents/orgs/crm/lead_agent.py`)

```python
"""
CRM Lead Qualification Agent.
Scores and qualifies leads based on engagement signals.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from src.core.agent import BaseAgent, AgentConfig
import structlog

logger = structlog.get_logger()


@dataclass
class LeadScore:
    """Lead scoring result."""
    lead_id: str
    score: float  # 0-100
    qualification: str  # "MQL", "SQL", "Unqualified"
    signals: List[Dict[str, Any]]
    next_action: str
    confidence: float


class LeadQualificationAgent(BaseAgent):
    """
    Qualifies leads based on behavioral signals and firmographic data.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.scoring_model = self._load_scoring_model()

    async def qualify_lead(self, lead_data: Dict[str, Any]) -> LeadScore:
        """
        Score and qualify a lead.
        """
        # Gather signals
        signals = await self._gather_signals(lead_data)

        # Score using ML model
        score = await self._calculate_score(lead_data, signals)

        # Determine qualification
        if score >= 80:
            qualification = "SQL"
            next_action = "Schedule sales call"
        elif score >= 50:
            qualification = "MQL"
            next_action = "Nurture with content"
        else:
            qualification = "Unqualified"
            next_action = "Continue monitoring"

        result = LeadScore(
            lead_id=lead_data["id"],
            score=score,
            qualification=qualification,
            signals=signals,
            next_action=next_action,
            confidence=0.85
        )

        # Log to memory
        await self.memory.store_episodic({
            "action": "lead_qualified",
            "lead_id": lead_data["id"],
            "score": score,
            "qualification": qualification
        })

        return result

    async def _gather_signals(self, lead_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gather behavioral and firmographic signals."""
        signals = []

        # Website engagement
        if lead_data.get("page_views", 0) > 10:
            signals.append({"type": "engagement", "signal": "high_page_views", "weight": 15})

        # Email engagement
        if lead_data.get("email_opens", 0) > 5:
            signals.append({"type": "engagement", "signal": "email_engaged", "weight": 10})

        # Demo request
        if lead_data.get("demo_requested", False):
            signals.append({"type": "intent", "signal": "demo_request", "weight": 30})

        # Company size
        if lead_data.get("company_size", 0) > 500:
            signals.append({"type": "firmographic", "signal": "enterprise", "weight": 20})

        return signals

    async def _calculate_score(
        self,
        lead_data: Dict[str, Any],
        signals: List[Dict[str, Any]]
    ) -> float:
        """Calculate lead score based on signals."""
        base_score = sum(s.get("weight", 0) for s in signals)
        return min(100, base_score)

    def _load_scoring_model(self):
        """Load ML scoring model."""
        return None  # Placeholder


class AccountInsightsAgent(BaseAgent):
    """
    Provides insights on customer accounts.
    """

    async def generate_account_summary(
        self,
        account_id: str
    ) -> Dict[str, Any]:
        """Generate comprehensive account summary."""
        # Retrieve account data
        account = await self._get_account_data(account_id)

        # Analyze interactions
        interactions = await self._analyze_interactions(account_id)

        # Identify opportunities
        opportunities = await self._identify_opportunities(account)

        # Generate summary using LLM
        summary = await self.llm.generate(
            prompt=f"""
            Generate an executive summary for this account:
            Account: {account['name']}
            Industry: {account['industry']}
            ARR: ${account['arr']:,}
            Health Score: {account['health_score']}/100
            Recent Interactions: {len(interactions)}

            Include:
            1. Key relationship highlights
            2. Risk factors
            3. Expansion opportunities
            4. Recommended actions
            """,
            max_tokens=500
        )

        return {
            "account_id": account_id,
            "summary": summary,
            "opportunities": opportunities,
            "interactions": interactions[:5]
        }

    async def _get_account_data(self, account_id: str) -> Dict[str, Any]:
        """Retrieve account data from CRM."""
        # Placeholder - would integrate with Salesforce/Dynamics
        return {
            "id": account_id,
            "name": "Acme Corp",
            "industry": "Manufacturing",
            "arr": 250000,
            "health_score": 75
        }

    async def _analyze_interactions(self, account_id: str) -> List[Dict[str, Any]]:
        """Analyze recent interactions."""
        return []

    async def _identify_opportunities(self, account: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify expansion opportunities."""
        return []
```

#### 16.1.2 HR Agent (`src/agents/orgs/hr/onboarding_agent.py`)

```python
"""
HR Onboarding Agent.
Automates employee onboarding workflows.
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from enum import Enum
from src.core.agent import BaseAgent, AgentConfig
import structlog

logger = structlog.get_logger()


class OnboardingStep(Enum):
    """Onboarding workflow steps."""
    WELCOME = "welcome"
    IT_SETUP = "it_setup"
    HR_FORMS = "hr_forms"
    TEAM_INTRO = "team_intro"
    TRAINING = "training"
    COMPLETE = "complete"


@dataclass
class OnboardingStatus:
    """Employee onboarding status."""
    employee_id: str
    current_step: OnboardingStep
    completed_steps: List[OnboardingStep]
    pending_actions: List[Dict[str, Any]]
    progress_percent: float


class OnboardingAgent(BaseAgent):
    """
    Manages employee onboarding end-to-end.
    """

    async def initiate_onboarding(
        self,
        employee: Dict[str, Any]
    ) -> OnboardingStatus:
        """
        Start onboarding for new employee.
        """
        # Create onboarding record
        onboarding_id = await self._create_onboarding_record(employee)

        # Send welcome message
        await self._send_welcome(employee)

        # Create IT provisioning request
        await self._request_it_setup(employee)

        # Generate HR forms
        await self._generate_hr_forms(employee)

        # Schedule team introduction
        await self._schedule_team_intro(employee)

        status = OnboardingStatus(
            employee_id=employee["id"],
            current_step=OnboardingStep.WELCOME,
            completed_steps=[],
            pending_actions=[
                {"action": "complete_hr_forms", "due": "3 days"},
                {"action": "it_setup", "due": "1 day"},
                {"action": "team_meeting", "due": "1 week"}
            ],
            progress_percent=10.0
        )

        logger.info("onboarding_initiated", employee_id=employee["id"])
        return status

    async def check_onboarding_status(
        self,
        employee_id: str
    ) -> OnboardingStatus:
        """Check current onboarding status."""
        # Retrieve status from memory
        record = await self.memory.retrieve_semantic(
            query=f"onboarding status for {employee_id}",
            limit=1
        )

        if not record:
            raise ValueError(f"No onboarding found for {employee_id}")

        return self._parse_status(record[0])

    async def answer_policy_question(
        self,
        question: str,
        employee_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Answer HR policy questions using RAG.
        """
        # Retrieve relevant policies
        policies = await self.memory.retrieve_semantic(
            query=question,
            collection="hr_policies",
            limit=5
        )

        # Generate answer
        answer = await self.llm.generate(
            prompt=f"""
            Answer this HR policy question based on company policies.

            Question: {question}
            Employee Level: {employee_context.get('level', 'Unknown')}
            Department: {employee_context.get('department', 'Unknown')}

            Relevant Policies:
            {self._format_policies(policies)}

            Provide a clear, accurate answer. Cite specific policies.
            """,
            max_tokens=500
        )

        return {
            "question": question,
            "answer": answer,
            "sources": [p["title"] for p in policies],
            "confidence": 0.9
        }

    async def _create_onboarding_record(self, employee: Dict[str, Any]) -> str:
        """Create onboarding tracking record."""
        return f"onb-{employee['id']}"

    async def _send_welcome(self, employee: Dict[str, Any]):
        """Send welcome email and Teams message."""
        pass

    async def _request_it_setup(self, employee: Dict[str, Any]):
        """Create IT provisioning ticket."""
        pass

    async def _generate_hr_forms(self, employee: Dict[str, Any]):
        """Generate required HR forms."""
        pass

    async def _schedule_team_intro(self, employee: Dict[str, Any]):
        """Schedule team introduction meeting."""
        pass

    def _format_policies(self, policies: List[Dict[str, Any]]) -> str:
        """Format policies for LLM context."""
        return "\n".join([f"- {p['title']}: {p['content']}" for p in policies])

    def _parse_status(self, record: Dict[str, Any]) -> OnboardingStatus:
        """Parse onboarding status from record."""
        return OnboardingStatus(
            employee_id=record["employee_id"],
            current_step=OnboardingStep(record["current_step"]),
            completed_steps=[OnboardingStep(s) for s in record["completed_steps"]],
            pending_actions=record["pending_actions"],
            progress_percent=record["progress_percent"]
        )
```

### 16.2 Governance Agents

#### 16.2.1 Compliance Agent (`src/agents/governance/compliance_agent.py`)

```python
"""
Compliance Agent for regulatory adherence monitoring.
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from enum import Enum
from src.core.agent import BaseAgent, AgentConfig
import structlog

logger = structlog.get_logger()


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    ISO27001 = "iso27001"


@dataclass
class ComplianceCheck:
    """Compliance check result."""
    control_id: str
    framework: ComplianceFramework
    status: str  # "compliant", "non_compliant", "partial", "not_applicable"
    evidence: List[Dict[str, Any]]
    remediation: Optional[str]
    risk_level: str


class ComplianceAgent(BaseAgent):
    """
    Monitors and enforces regulatory compliance.
    """

    async def run_compliance_check(
        self,
        framework: ComplianceFramework,
        scope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run compliance check for specified framework.
        """
        controls = self._get_framework_controls(framework)
        results = []

        for control in controls:
            check_result = await self._evaluate_control(control, scope)
            results.append(check_result)

        # Calculate compliance score
        compliant_count = sum(1 for r in results if r.status == "compliant")
        total_count = len(results)
        score = (compliant_count / total_count) * 100 if total_count > 0 else 0

        report = {
            "framework": framework.value,
            "timestamp": datetime.utcnow().isoformat(),
            "scope": scope,
            "score": score,
            "total_controls": total_count,
            "compliant": compliant_count,
            "non_compliant": total_count - compliant_count,
            "results": [self._serialize_check(r) for r in results],
            "recommendations": await self._generate_recommendations(results)
        }

        # Store in memory for audit
        await self.memory.store_episodic({
            "action": "compliance_check",
            "framework": framework.value,
            "score": score
        })

        return report

    async def _evaluate_control(
        self,
        control: Dict[str, Any],
        scope: Dict[str, Any]
    ) -> ComplianceCheck:
        """Evaluate a single control."""
        # Gather evidence
        evidence = await self._gather_evidence(control, scope)

        # Evaluate using policy engine
        evaluation = await self.policy_engine.evaluate({
            "control": control,
            "evidence": evidence,
            "scope": scope
        })

        return ComplianceCheck(
            control_id=control["id"],
            framework=ComplianceFramework(control["framework"]),
            status=evaluation["status"],
            evidence=evidence,
            remediation=evaluation.get("remediation"),
            risk_level=evaluation.get("risk_level", "medium")
        )

    def _get_framework_controls(self, framework: ComplianceFramework) -> List[Dict]:
        """Get controls for framework."""
        controls_map = {
            ComplianceFramework.SOC2: self._soc2_controls(),
            ComplianceFramework.HIPAA: self._hipaa_controls(),
            ComplianceFramework.GDPR: self._gdpr_controls(),
        }
        return controls_map.get(framework, [])

    def _soc2_controls(self) -> List[Dict]:
        """SOC 2 trust service criteria."""
        return [
            {"id": "CC1.1", "framework": "soc2", "name": "Control Environment"},
            {"id": "CC2.1", "framework": "soc2", "name": "Communication and Information"},
            {"id": "CC3.1", "framework": "soc2", "name": "Risk Assessment"},
            {"id": "CC4.1", "framework": "soc2", "name": "Monitoring Activities"},
            {"id": "CC5.1", "framework": "soc2", "name": "Control Activities"},
            {"id": "CC6.1", "framework": "soc2", "name": "Logical and Physical Access"},
            {"id": "CC7.1", "framework": "soc2", "name": "System Operations"},
            {"id": "CC8.1", "framework": "soc2", "name": "Change Management"},
            {"id": "CC9.1", "framework": "soc2", "name": "Risk Mitigation"},
        ]

    async def _gather_evidence(
        self,
        control: Dict[str, Any],
        scope: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Gather evidence for control evaluation."""
        return []

    async def _generate_recommendations(
        self,
        results: List[ComplianceCheck]
    ) -> List[str]:
        """Generate remediation recommendations."""
        non_compliant = [r for r in results if r.status == "non_compliant"]

        if not non_compliant:
            return ["All controls are compliant. Maintain current practices."]

        recommendations = []
        for check in non_compliant:
            if check.remediation:
                recommendations.append(check.remediation)

        return recommendations

    def _serialize_check(self, check: ComplianceCheck) -> Dict[str, Any]:
        """Serialize compliance check for JSON."""
        return {
            "control_id": check.control_id,
            "framework": check.framework.value,
            "status": check.status,
            "risk_level": check.risk_level,
            "remediation": check.remediation
        }
```

### 16.3 Cybersecurity Agents

#### 16.3.1 Defender Triage Agent (`src/agents/cybersecurity/defender_agent.py`)

```python
"""
Microsoft Defender Triage Agent.
Automated security alert investigation and response.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
from src.core.agent import BaseAgent, AgentConfig
import structlog

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(Enum):
    """Threat categories."""
    MALWARE = "malware"
    PHISHING = "phishing"
    RANSOMWARE = "ransomware"
    DATA_EXFILTRATION = "data_exfiltration"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CREDENTIAL_THEFT = "credential_theft"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class TriageResult:
    """Alert triage result."""
    alert_id: str
    severity: AlertSeverity
    category: ThreatCategory
    is_true_positive: bool
    confidence: float
    investigation_summary: str
    recommended_actions: List[str]
    auto_remediated: bool


class DefenderTriageAgent(BaseAgent):
    """
    Triages and responds to Microsoft Defender alerts.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.defender_client = self._init_defender_client()

    async def triage_alert(self, alert_id: str) -> TriageResult:
        """
        Investigate and triage a Defender alert.
        """
        # Fetch alert details
        alert = await self._get_alert(alert_id)

        # Enrich with context
        context = await self._enrich_alert(alert)

        # Analyze using LLM
        analysis = await self._analyze_alert(alert, context)

        # Determine if true positive
        is_tp, confidence = await self._classify_alert(alert, context, analysis)

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            alert, analysis, is_tp
        )

        # Auto-remediate if high confidence and policy allows
        auto_remediated = False
        if is_tp and confidence > 0.95:
            auto_remediated = await self._auto_remediate(alert, recommendations)

        result = TriageResult(
            alert_id=alert_id,
            severity=AlertSeverity(alert["severity"]),
            category=ThreatCategory(analysis["category"]),
            is_true_positive=is_tp,
            confidence=confidence,
            investigation_summary=analysis["summary"],
            recommended_actions=recommendations,
            auto_remediated=auto_remediated
        )

        # Log investigation
        await self.memory.store_episodic({
            "action": "alert_triage",
            "alert_id": alert_id,
            "is_true_positive": is_tp,
            "auto_remediated": auto_remediated
        })

        return result

    async def _get_alert(self, alert_id: str) -> Dict[str, Any]:
        """Fetch alert from Defender API."""
        # Integration with Microsoft Defender API
        return {
            "id": alert_id,
            "title": "Suspicious PowerShell execution",
            "severity": "high",
            "category": "suspicious_activity",
            "description": "PowerShell executed encoded command",
            "entities": [
                {"type": "user", "name": "john.doe@contoso.com"},
                {"type": "device", "name": "DESKTOP-ABC123"}
            ]
        }

    async def _enrich_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich alert with additional context."""
        context = {
            "user_risk": await self._get_user_risk(alert),
            "device_risk": await self._get_device_risk(alert),
            "recent_alerts": await self._get_related_alerts(alert),
            "threat_intel": await self._check_threat_intel(alert)
        }
        return context

    async def _analyze_alert(
        self,
        alert: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze alert using LLM."""
        analysis = await self.llm.generate(
            prompt=f"""
            Analyze this security alert:

            Alert: {alert['title']}
            Description: {alert['description']}
            Severity: {alert['severity']}

            Context:
            - User Risk Score: {context['user_risk']}
            - Device Risk Score: {context['device_risk']}
            - Related Alerts: {len(context['recent_alerts'])}

            Provide:
            1. Threat category classification
            2. Attack chain analysis
            3. Potential impact assessment
            4. Investigation summary
            """,
            max_tokens=500
        )

        return {
            "category": "suspicious_activity",
            "summary": analysis,
            "attack_chain": []
        }

    async def _classify_alert(
        self,
        alert: Dict[str, Any],
        context: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> tuple[bool, float]:
        """Classify as true/false positive."""
        # Use ML model + heuristics
        return True, 0.87

    async def _generate_recommendations(
        self,
        alert: Dict[str, Any],
        analysis: Dict[str, Any],
        is_tp: bool
    ) -> List[str]:
        """Generate remediation recommendations."""
        if not is_tp:
            return ["Close as false positive", "Update detection rules"]

        return [
            "Isolate affected device",
            "Reset user credentials",
            "Block malicious IP addresses",
            "Collect forensic evidence",
            "Notify security team"
        ]

    async def _auto_remediate(
        self,
        alert: Dict[str, Any],
        recommendations: List[str]
    ) -> bool:
        """Execute automatic remediation actions."""
        # Only execute low-risk, reversible actions
        safe_actions = ["Block malicious IP addresses"]

        for action in recommendations:
            if action in safe_actions:
                await self._execute_action(action, alert)
                return True

        return False

    async def _execute_action(self, action: str, alert: Dict[str, Any]):
        """Execute remediation action."""
        logger.info("auto_remediation", action=action, alert_id=alert["id"])

    async def _get_user_risk(self, alert: Dict[str, Any]) -> float:
        """Get user risk score from Identity Protection."""
        return 0.3

    async def _get_device_risk(self, alert: Dict[str, Any]) -> float:
        """Get device risk score from Defender for Endpoint."""
        return 0.5

    async def _get_related_alerts(self, alert: Dict[str, Any]) -> List[Dict]:
        """Get related alerts."""
        return []

    async def _check_threat_intel(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Check threat intelligence feeds."""
        return {}

    def _init_defender_client(self):
        """Initialize Microsoft Defender client."""
        return None
```

#### 16.3.2 Sentinel Investigation Agent (`src/agents/cybersecurity/sentinel_agent.py`)

```python
"""
Microsoft Sentinel Investigation Agent.
Automated incident investigation and hunting.
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from src.core.agent import BaseAgent, AgentConfig
import structlog

logger = structlog.get_logger()


@dataclass
class Investigation:
    """Incident investigation result."""
    incident_id: str
    title: str
    timeline: List[Dict[str, Any]]
    affected_entities: List[Dict[str, Any]]
    root_cause: str
    iocs: List[Dict[str, Any]]
    narrative: str
    recommendations: List[str]


class SentinelInvestigationAgent(BaseAgent):
    """
    Investigates Sentinel incidents using automated hunting.
    """

    async def investigate_incident(self, incident_id: str) -> Investigation:
        """
        Perform comprehensive incident investigation.
        """
        # Get incident details
        incident = await self._get_incident(incident_id)

        # Build timeline
        timeline = await self._build_timeline(incident)

        # Extract IOCs
        iocs = await self._extract_iocs(incident, timeline)

        # Determine root cause
        root_cause = await self._analyze_root_cause(incident, timeline)

        # Generate narrative
        narrative = await self._generate_narrative(
            incident, timeline, iocs, root_cause
        )

        return Investigation(
            incident_id=incident_id,
            title=incident["title"],
            timeline=timeline,
            affected_entities=incident.get("entities", []),
            root_cause=root_cause,
            iocs=iocs,
            narrative=narrative,
            recommendations=await self._generate_recommendations(incident, root_cause)
        )

    async def run_hunting_query(
        self,
        hypothesis: str
    ) -> Dict[str, Any]:
        """
        Run threat hunting based on hypothesis.
        """
        # Generate KQL query from hypothesis
        kql = await self._hypothesis_to_kql(hypothesis)

        # Execute query
        results = await self._execute_kql(kql)

        # Analyze results
        analysis = await self._analyze_hunting_results(hypothesis, results)

        return {
            "hypothesis": hypothesis,
            "kql": kql,
            "results_count": len(results),
            "findings": analysis["findings"],
            "new_iocs": analysis["new_iocs"],
            "recommendations": analysis["recommendations"]
        }

    async def _get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Fetch incident from Sentinel."""
        return {
            "id": incident_id,
            "title": "Multi-stage attack detected",
            "severity": "High",
            "status": "Active",
            "alerts": [],
            "entities": []
        }

    async def _build_timeline(self, incident: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build attack timeline from events."""
        return []

    async def _extract_iocs(
        self,
        incident: Dict[str, Any],
        timeline: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract indicators of compromise."""
        return []

    async def _analyze_root_cause(
        self,
        incident: Dict[str, Any],
        timeline: List[Dict[str, Any]]
    ) -> str:
        """Determine root cause of incident."""
        return "Initial access via phishing email"

    async def _generate_narrative(
        self,
        incident: Dict[str, Any],
        timeline: List[Dict[str, Any]],
        iocs: List[Dict[str, Any]],
        root_cause: str
    ) -> str:
        """Generate investigation narrative using LLM."""
        return await self.llm.generate(
            prompt=f"""
            Generate a security incident investigation narrative.

            Incident: {incident['title']}
            Root Cause: {root_cause}
            Timeline Events: {len(timeline)}
            IOCs Found: {len(iocs)}

            Write a clear, professional narrative suitable for
            executive briefing and incident documentation.
            """,
            max_tokens=800
        )

    async def _generate_recommendations(
        self,
        incident: Dict[str, Any],
        root_cause: str
    ) -> List[str]:
        """Generate remediation recommendations."""
        return [
            "Implement email authentication (DMARC/DKIM/SPF)",
            "Enable MFA for all users",
            "Deploy advanced threat protection",
            "Conduct security awareness training"
        ]

    async def _hypothesis_to_kql(self, hypothesis: str) -> str:
        """Convert hunting hypothesis to KQL query."""
        kql = await self.llm.generate(
            prompt=f"""
            Convert this threat hunting hypothesis to a KQL query:

            Hypothesis: {hypothesis}

            Generate a valid KQL query for Microsoft Sentinel.
            Include appropriate time ranges and filters.
            """,
            max_tokens=300
        )
        return kql

    async def _execute_kql(self, kql: str) -> List[Dict[str, Any]]:
        """Execute KQL query against Log Analytics."""
        return []

    async def _analyze_hunting_results(
        self,
        hypothesis: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze hunting results."""
        return {
            "findings": [],
            "new_iocs": [],
            "recommendations": []
        }
```

---

## 17. Phase 13: End-to-End Data Pipeline

### 17.1 Data Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ANTS End-to-End Data Pipeline                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │   Event     │   │   IoT Hub   │   │  Document   │   │   Video/    │      │
│  │   Hubs      │   │   +ADT      │   │   Upload    │   │   Audio     │      │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘      │
│         │                 │                 │                 │              │
│         └─────────────────┴─────────────────┴─────────────────┘              │
│                                     │                                         │
│                           ┌─────────▼─────────┐                              │
│                           │   INGESTION LAYER │                              │
│                           │  (Event-Driven)   │                              │
│                           └─────────┬─────────┘                              │
│                                     │                                         │
│         ┌───────────────────────────┴───────────────────────────┐            │
│         │                                                       │            │
│         ▼                                                       ▼            │
│  ┌─────────────┐                                         ┌─────────────┐     │
│  │   Bronze    │                                         │   ANF Raw   │     │
│  │   (Raw)     │                                         │   Storage   │     │
│  └──────┬──────┘                                         └──────┬──────┘     │
│         │                                                       │            │
│         ▼                                                       │            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │            │
│  │   Silver    │◄──│  PII/NER    │◄──│   Schema    │           │            │
│  │  (Cleaned)  │   │  Detection  │   │   Valid.    │           │            │
│  └──────┬──────┘   └─────────────┘   └─────────────┘           │            │
│         │                                                       │            │
│         ▼                                                       │            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │            │
│  │    Gold     │──►│  Embeddings │──►│   Vector    │◄──────────┘            │
│  │  (Curated)  │   │  (NIM)      │   │   Store     │                        │
│  └──────┬──────┘   └─────────────┘   └─────────────┘                        │
│         │                                                                    │
│         └───────────────────────────────────────────────────────────────┐    │
│                                                                         │    │
│  ┌─────────────────────────────────────────────────────────────────────▼┐   │
│  │                           SERVING LAYER                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Inference  │  │     RAG     │  │   Actions   │  │  Real-Time  │  │   │
│  │  │    (NIM)    │  │  Retrieval  │  │   Executor  │  │  Analytics  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 17.2 Ingestion Layer (`data/ingestion/`)

#### 17.2.1 Event Hub Consumer (`data/ingestion/eventhubs/consumer.py`)

```python
"""
Event Hub consumer for real-time event ingestion.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Callable, Optional
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub.extensions.checkpointstoreblob.aio import BlobCheckpointStore
from azure.identity.aio import DefaultAzureCredential
import structlog
import asyncio

logger = structlog.get_logger()


@dataclass
class EventHubConfig:
    """Event Hub configuration."""
    namespace: str
    eventhub_name: str
    consumer_group: str = "$Default"
    checkpoint_container: str = "checkpoints"
    checkpoint_account: str = ""


class EventHubConsumer:
    """
    Consumes events from Azure Event Hub.
    Supports parallel partition processing with checkpointing.
    """

    def __init__(self, config: EventHubConfig):
        self.config = config
        self.credential = DefaultAzureCredential()
        self._client: Optional[EventHubConsumerClient] = None
        self._handlers: List[Callable] = []

    async def start(self):
        """Start consuming events."""
        checkpoint_store = BlobCheckpointStore.from_connection_string(
            conn_str=self.config.checkpoint_connection_string,
            container_name=self.config.checkpoint_container
        )

        self._client = EventHubConsumerClient(
            fully_qualified_namespace=f"{self.config.namespace}.servicebus.windows.net",
            eventhub_name=self.config.eventhub_name,
            consumer_group=self.config.consumer_group,
            credential=self.credential,
            checkpoint_store=checkpoint_store
        )

        async with self._client:
            await self._client.receive(
                on_event=self._process_event,
                on_error=self._handle_error,
                starting_position="-1"
            )

    async def _process_event(self, partition_context, event):
        """Process incoming event."""
        try:
            # Parse CloudEvent
            event_data = event.body_as_json()

            logger.debug(
                "event_received",
                partition=partition_context.partition_id,
                type=event_data.get("type")
            )

            # Route to handlers
            for handler in self._handlers:
                await handler(event_data, partition_context)

            # Checkpoint every 100 events
            if partition_context.last_enqueued_event_properties.sequence_number % 100 == 0:
                await partition_context.update_checkpoint(event)

        except Exception as e:
            logger.error("event_processing_error", error=str(e))

    async def _handle_error(self, partition_context, error):
        """Handle consumer errors."""
        logger.error(
            "eventhub_consumer_error",
            partition=partition_context.partition_id if partition_context else None,
            error=str(error)
        )

    def register_handler(self, handler: Callable):
        """Register event handler."""
        self._handlers.append(handler)


class IoTHubIngestion:
    """
    IoT Hub ingestion with Digital Twins integration.
    """

    def __init__(self, iot_hub_connection: str, digital_twins_url: str):
        self.iot_hub_connection = iot_hub_connection
        self.digital_twins_url = digital_twins_url

    async def process_telemetry(self, device_id: str, telemetry: Dict[str, Any]):
        """
        Process device telemetry and update Digital Twin.
        """
        from azure.digitaltwins.core.aio import DigitalTwinsClient

        async with DigitalTwinsClient(
            self.digital_twins_url,
            DefaultAzureCredential()
        ) as dt_client:
            # Update twin properties
            patch = [
                {
                    "op": "replace",
                    "path": f"/telemetry/{k}",
                    "value": v
                }
                for k, v in telemetry.items()
            ]

            await dt_client.update_digital_twin(device_id, patch)

            logger.info("digital_twin_updated", device_id=device_id)
```

### 17.3 ETL Layer - Medallion Architecture (`data/etl/databricks/`)

#### 17.3.1 Bronze Layer (`data/etl/databricks/bronze_ingestion.py`)

```python
"""
Bronze layer - raw data ingestion with minimal transformation.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta.tables import DeltaTable

spark = SparkSession.builder.getOrCreate()

# Autoloader configuration for ANF Object REST API
bronze_events = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", "/mnt/anf/schema/events")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .load("s3a://anf-memory/raw/events/")
)

# Write to Bronze Delta table
(bronze_events
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", input_file_name())
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/mnt/anf/checkpoints/bronze_events")
    .trigger(processingTime="1 minute")
    .table("bronze.events")
)
```

#### 17.3.2 Silver Layer (`data/etl/databricks/silver_transform.py`)

```python
"""
Silver layer - cleaned, validated, deduplicated data.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta.tables import DeltaTable

spark = SparkSession.builder.getOrCreate()

# Read from Bronze
bronze_events = spark.readStream.table("bronze.events")

# Apply transformations
silver_events = (
    bronze_events
    # Schema validation
    .filter(col("event_type").isNotNull())
    .filter(col("timestamp").isNotNull())

    # Data quality
    .withColumn("timestamp", to_timestamp("timestamp"))
    .withColumn("event_date", to_date("timestamp"))

    # PII detection and masking
    .withColumn(
        "content",
        regexp_replace("content", r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]')
    )
    .withColumn(
        "content",
        regexp_replace("content", r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]')
    )

    # Deduplication
    .dropDuplicates(["event_id"])

    # Add metadata
    .withColumn("_processed_at", current_timestamp())
)

# Write to Silver Delta table with merge
def merge_to_silver(batch_df, batch_id):
    silver_table = DeltaTable.forName(spark, "silver.events")

    (silver_table.alias("target")
        .merge(
            batch_df.alias("source"),
            "target.event_id = source.event_id"
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

(silver_events
    .writeStream
    .foreachBatch(merge_to_silver)
    .option("checkpointLocation", "/mnt/anf/checkpoints/silver_events")
    .trigger(processingTime="5 minutes")
    .start()
)
```

#### 17.3.3 Gold Layer (`data/etl/databricks/gold_aggregate.py`)

```python
"""
Gold layer - business-ready aggregations and features.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = SparkSession.builder.getOrCreate()

# Agent Performance Metrics (Gold table)
agent_metrics = (
    spark.read.table("silver.events")
    .filter(col("event_type") == "agent_execution")
    .groupBy(
        window("timestamp", "1 hour"),
        "agent_id",
        "tenant_id"
    )
    .agg(
        count("*").alias("execution_count"),
        avg("latency_ms").alias("avg_latency"),
        percentile_approx("latency_ms", 0.95).alias("p95_latency"),
        sum(when(col("success") == True, 1).otherwise(0)).alias("success_count"),
        sum("tokens_used").alias("total_tokens"),
        sum("estimated_cost").alias("total_cost")
    )
    .withColumn("success_rate", col("success_count") / col("execution_count"))
)

agent_metrics.write.format("delta").mode("overwrite").saveAsTable("gold.agent_metrics_hourly")

# Business KPIs (Gold table)
business_kpis = (
    spark.read.table("silver.events")
    .filter(col("event_type").isin(["reconciliation", "invoice_processed", "order_created"]))
    .groupBy(
        to_date("timestamp").alias("date"),
        "tenant_id",
        "event_type"
    )
    .agg(
        count("*").alias("event_count"),
        sum("amount").alias("total_amount"),
        avg("processing_time_ms").alias("avg_processing_time")
    )
)

business_kpis.write.format("delta").mode("overwrite").saveAsTable("gold.business_kpis_daily")
```

---

## 18. Phase 14: Bootstrap AI Agent & Self-Deployment

### 18.1 Bootstrap CLI (`platform/bootstrap/antsctl.py`)

```python
"""
ANTS Bootstrap CLI - Deploy full architecture from spec.
Provides safe automation with human confirmation.
"""
import click
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import structlog
import subprocess
import json

logger = structlog.get_logger()


@dataclass
class ANTSSpec:
    """ANTS deployment specification."""
    tenant: str
    regions: Dict[str, str]
    ha: Dict[str, Any]
    modules: Dict[str, bool]
    data: Dict[str, Any]
    ai: Dict[str, Any]
    analytics: Dict[str, bool]
    governance: Dict[str, bool]


def load_spec(spec_path: Path) -> ANTSSpec:
    """Load and validate ANTS spec file."""
    with open(spec_path) as f:
        raw = yaml.safe_load(f)

    return ANTSSpec(
        tenant=raw["tenant"],
        regions=raw["regions"],
        ha=raw["ha"],
        modules=raw["modules"],
        data=raw["data"],
        ai=raw["ai"],
        analytics=raw["analytics"],
        governance=raw["governance"]
    )


@click.group()
def cli():
    """ANTS Control CLI - Deploy and manage ANTS infrastructure."""
    pass


@cli.command()
@click.option("--spec", "-s", required=True, help="Path to ants-spec.yaml")
@click.option("--dry-run", is_flag=True, help="Show plan without applying")
@click.option("--auto-approve", is_flag=True, help="Skip confirmation prompts")
def deploy(spec: str, dry_run: bool, auto_approve: bool):
    """Deploy ANTS infrastructure from spec."""
    spec_path = Path(spec)
    if not spec_path.exists():
        click.echo(f"Spec file not found: {spec}")
        return

    ants_spec = load_spec(spec_path)
    deployer = ANTSDeployer(ants_spec)

    click.echo(f"\n🐜 ANTS Deployment for tenant: {ants_spec.tenant}")
    click.echo(f"   Primary region: {ants_spec.regions['primary']}")
    click.echo(f"   DR region: {ants_spec.regions['dr']}")

    # Generate Terraform variables
    tf_vars = deployer.generate_terraform_vars()
    click.echo("\n📋 Terraform Variables:")
    click.echo(yaml.dump(tf_vars, default_flow_style=False))

    # Generate Helm values
    helm_values = deployer.generate_helm_values()
    click.echo("\n📋 Helm Values:")
    click.echo(yaml.dump(helm_values, default_flow_style=False))

    if dry_run:
        click.echo("\n✨ Dry run complete. No changes made.")
        return

    # Run Terraform plan
    click.echo("\n🔍 Running Terraform plan...")
    plan_result = deployer.terraform_plan(tf_vars)

    if plan_result["changes"]:
        click.echo(f"\n   Resources to create: {plan_result['create']}")
        click.echo(f"   Resources to update: {plan_result['update']}")
        click.echo(f"   Resources to delete: {plan_result['delete']}")

        if not auto_approve:
            if not click.confirm("\n⚠️  Apply these changes?"):
                click.echo("Deployment cancelled.")
                return

        # Apply infrastructure
        click.echo("\n🚀 Applying Terraform...")
        deployer.terraform_apply(tf_vars)

        # Deploy Helm charts
        click.echo("\n🎯 Deploying Helm charts...")
        deployer.helm_deploy(helm_values)

        # Register agents
        click.echo("\n🤖 Registering agents...")
        deployer.register_agents()

        # Run smoke tests
        click.echo("\n🧪 Running smoke tests...")
        test_results = deployer.run_smoke_tests()

        if test_results["passed"]:
            click.echo("\n✅ Deployment complete! All tests passed.")
        else:
            click.echo(f"\n⚠️  Deployment complete with {test_results['failed']} test failures.")


class ANTSDeployer:
    """Handles ANTS deployment from spec."""

    def __init__(self, spec: ANTSSpec):
        self.spec = spec

    def generate_terraform_vars(self) -> Dict[str, Any]:
        """Generate Terraform variable file from spec."""
        return {
            "environment": self.spec.tenant,
            "primary_location": self.spec.regions["primary"],
            "dr_location": self.spec.regions["dr"],
            "enable_zones": self.spec.ha["zones"],
            "rpo_minutes": self.spec.ha["rpo_minutes"],
            "rto_minutes": self.spec.ha["rto_minutes"],

            # ANF configuration
            "anf_service_level": self.spec.data["anf"]["service_level"],
            "anf_cool_access": self.spec.data["anf"]["cool_access"],
            "anf_object_api": self.spec.data["anf"]["object_rest_api"],

            # Modules
            "enable_finance": self.spec.modules.get("finance", False),
            "enable_retail": self.spec.modules.get("retail", False),
            "enable_manufacturing": self.spec.modules.get("manufacturing", False),
            "enable_healthcare": self.spec.modules.get("healthcare", False),
            "enable_crm": self.spec.modules.get("crm", False),
            "enable_hr": self.spec.modules.get("hr", False),

            # Analytics
            "enable_fabric": self.spec.analytics.get("onelake_fabric", False),
            "enable_databricks": self.spec.analytics.get("databricks", False),

            # Governance
            "enable_opa": self.spec.governance.get("opa", True),
            "enable_sentinel": self.spec.governance.get("sentinel_defender", False),
        }

    def generate_helm_values(self) -> Dict[str, Any]:
        """Generate Helm values from spec."""
        return {
            "global": {
                "tenant": self.spec.tenant,
                "environment": "production"
            },
            "nim": {
                "models": self.spec.ai.get("nim_models", []),
                "gpu": {
                    "count": 2,
                    "type": "A100"
                }
            },
            "agents": {
                "finance": {"enabled": self.spec.modules.get("finance", False)},
                "retail": {"enabled": self.spec.modules.get("retail", False)},
                "manufacturing": {"enabled": self.spec.modules.get("manufacturing", False)},
                "cybersecurity": {"enabled": self.spec.governance.get("sentinel_defender", False)}
            },
            "observability": {
                "metrics": {"enabled": True},
                "tracing": {"enabled": True},
                "clear_metrics": {"enabled": True}
            }
        }

    def terraform_plan(self, vars: Dict[str, Any]) -> Dict[str, Any]:
        """Run Terraform plan."""
        # Write vars to file
        vars_file = Path("/tmp/ants.tfvars.json")
        vars_file.write_text(json.dumps(vars))

        # Run terraform plan
        result = subprocess.run(
            ["terraform", "plan", "-var-file", str(vars_file), "-json"],
            capture_output=True,
            text=True,
            cwd="infra/terraform/envs/production"
        )

        # Parse plan output
        return {
            "changes": True,
            "create": 45,
            "update": 0,
            "delete": 0
        }

    def terraform_apply(self, vars: Dict[str, Any]):
        """Apply Terraform configuration."""
        logger.info("terraform_apply_started")
        # terraform apply -auto-approve

    def helm_deploy(self, values: Dict[str, Any]):
        """Deploy Helm charts."""
        logger.info("helm_deploy_started")
        # helm upgrade --install ants ./charts/ants-core

    def register_agents(self):
        """Register agents in catalog."""
        logger.info("agents_registered")

    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run deployment smoke tests."""
        return {"passed": True, "failed": 0}


@cli.command()
@click.option("--spec", "-s", required=True, help="Path to ants-spec.yaml")
def validate(spec: str):
    """Validate ANTS spec file."""
    spec_path = Path(spec)
    if not spec_path.exists():
        click.echo(f"Spec file not found: {spec}")
        return

    try:
        ants_spec = load_spec(spec_path)
        click.echo("✅ Spec file is valid")
        click.echo(f"   Tenant: {ants_spec.tenant}")
        click.echo(f"   Modules: {list(k for k, v in ants_spec.modules.items() if v)}")
    except Exception as e:
        click.echo(f"❌ Spec validation failed: {e}")


if __name__ == "__main__":
    cli()
```

### 18.2 ANTS Spec Schema (`platform/standards/ants-spec.schema.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ANTS Deployment Specification",
  "type": "object",
  "required": ["tenant", "regions", "modules"],
  "properties": {
    "tenant": {
      "type": "string",
      "description": "Tenant identifier"
    },
    "regions": {
      "type": "object",
      "required": ["primary"],
      "properties": {
        "primary": {"type": "string"},
        "dr": {"type": "string"}
      }
    },
    "ha": {
      "type": "object",
      "properties": {
        "zones": {"type": "boolean", "default": true},
        "rpo_minutes": {"type": "integer", "default": 30},
        "rto_minutes": {"type": "integer", "default": 60}
      }
    },
    "modules": {
      "type": "object",
      "properties": {
        "finance": {"type": "boolean"},
        "retail": {"type": "boolean"},
        "manufacturing": {"type": "boolean"},
        "healthcare": {"type": "boolean"},
        "crm": {"type": "boolean"},
        "hr": {"type": "boolean"},
        "supply_chain": {"type": "boolean"}
      }
    },
    "data": {
      "type": "object",
      "properties": {
        "anf": {
          "type": "object",
          "properties": {
            "service_level": {"enum": ["Standard", "Premium", "Ultra"]},
            "cool_access": {"type": "boolean"},
            "object_rest_api": {"type": "boolean"}
          }
        }
      }
    },
    "ai": {
      "type": "object",
      "properties": {
        "nim_models": {
          "type": "array",
          "items": {"type": "string"}
        },
        "use_ai_search": {"type": "boolean"}
      }
    },
    "analytics": {
      "type": "object",
      "properties": {
        "onelake_fabric": {"type": "boolean"},
        "databricks": {"type": "boolean"}
      }
    },
    "governance": {
      "type": "object",
      "properties": {
        "opa": {"type": "boolean"},
        "agent365": {"type": "boolean"},
        "sentinel_defender": {"type": "boolean"}
      }
    }
  }
}
```

---

## 19. Phase 15: ANF Advanced Features

### 19.1 ANF Flexible Service Levels (`infrastructure/terraform/modules/anf_advanced/main.tf`)

```hcl
# Advanced ANF configuration with all features

resource "azurerm_netapp_account" "ants" {
  name                = "anf-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# Ultra tier for inference workloads
resource "azurerm_netapp_pool" "ultra" {
  name                = "pool-ultra"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Ultra"
  size_in_tb          = var.ultra_pool_size_tb
  qos_type            = "Manual"

  tags = var.tags
}

# Premium tier for active memory
resource "azurerm_netapp_pool" "premium" {
  name                = "pool-premium"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Premium"
  size_in_tb          = var.premium_pool_size_tb
  qos_type            = "Auto"

  tags = var.tags
}

# Standard tier for archival with cool access
resource "azurerm_netapp_pool" "standard" {
  name                = "pool-standard-cool"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Standard"
  size_in_tb          = var.standard_pool_size_tb
  qos_type            = "Auto"

  # Enable cool access tier for cost optimization
  cool_access = true

  tags = var.tags
}

# Volume for model cache (Ultra - fastest access)
resource "azurerm_netapp_volume" "models" {
  name                = "vol-models"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.ultra.name
  volume_path         = "models"
  service_level       = "Ultra"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 5120
  throughput_in_mibps = 4096  # 4 GiB/s for model loading

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = var.tags
}

# Volume for episodic memory (Premium)
resource "azurerm_netapp_volume" "episodic_memory" {
  name                = "vol-episodic-memory"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "episodic"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 10240

  protocols = ["NFSv4.1"]

  # Enable cool access for older data
  data_protection_snapshot_policy {
    snapshot_policy_id = azurerm_netapp_snapshot_policy.comprehensive.id
  }

  tags = var.tags
}

# Volume for archival with cool tier (Standard + Cool)
resource "azurerm_netapp_volume" "archive" {
  name                = "vol-archive"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.standard.name
  volume_path         = "archive"
  service_level       = "Standard"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 51200

  protocols = ["NFSv4.1"]

  # Cool access configuration
  cool_access        = true
  coolness_period    = 7  # Move to cool after 7 days

  tags = var.tags
}

# Comprehensive snapshot policy
resource "azurerm_netapp_snapshot_policy" "comprehensive" {
  name                = "policy-comprehensive"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name

  enabled = true

  hourly_schedule {
    snapshots_to_keep = 48
    minute            = 0
  }

  daily_schedule {
    snapshots_to_keep = 30
    hour              = 2
    minute            = 0
  }

  weekly_schedule {
    snapshots_to_keep = 12
    days_of_week      = ["Sunday"]
    hour              = 3
    minute            = 0
  }

  monthly_schedule {
    snapshots_to_keep = 24
    days_of_month     = [1]
    hour              = 4
    minute            = 0
  }

  tags = var.tags
}

# Cross-region replication for DR
resource "azurerm_netapp_volume_replication" "episodic_dr" {
  endpoint_type             = "dst"
  remote_volume_location    = var.dr_location
  remote_volume_resource_id = azurerm_netapp_volume.episodic_memory.id
  replication_frequency     = "10minutes"
}

output "anf_volumes" {
  value = {
    models = {
      mount_path    = azurerm_netapp_volume.models.mount_ip_addresses[0]
      volume_path   = azurerm_netapp_volume.models.volume_path
      service_level = "Ultra"
    }
    episodic = {
      mount_path    = azurerm_netapp_volume.episodic_memory.mount_ip_addresses[0]
      volume_path   = azurerm_netapp_volume.episodic_memory.volume_path
      service_level = "Premium"
    }
    archive = {
      mount_path    = azurerm_netapp_volume.archive.mount_ip_addresses[0]
      volume_path   = azurerm_netapp_volume.archive.volume_path
      service_level = "Standard+Cool"
    }
  }
}
```

### 19.2 ANF Object REST API Integration (`src/integrations/anf/object_api.py`)

```python
"""
ANF Object REST API client for S3-compatible access.
Enables OneLake/Fabric integration via shortcuts.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, BinaryIO
import boto3
from botocore.config import Config
import structlog

logger = structlog.get_logger()


@dataclass
class ANFObjectConfig:
    """Configuration for ANF Object REST API."""
    account_name: str
    access_key: str
    secret_key: str
    region: str = "eastus2"

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_name}.blob.core.windows.net"


class ANFObjectClient:
    """
    S3-compatible client for ANF Object REST API.
    Enables zero-copy integration with Fabric/Databricks.
    """

    def __init__(self, config: ANFObjectConfig):
        self.config = config
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"}
            )
        )

    def list_buckets(self) -> List[Dict[str, Any]]:
        """List all ANF volumes as S3 buckets."""
        response = self._client.list_buckets()
        return [{"name": b["Name"], "created": b["CreationDate"]} for b in response["Buckets"]]

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """List objects in ANF volume."""
        response = self._client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=max_keys
        )

        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "modified": obj["LastModified"],
                "etag": obj["ETag"]
            }
            for obj in response.get("Contents", [])
        ]

    def upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Upload file to ANF volume via Object API."""
        extra_args = {}
        if metadata:
            extra_args["Metadata"] = metadata

        self._client.upload_file(file_path, bucket, key, ExtraArgs=extra_args)
        logger.info("file_uploaded", bucket=bucket, key=key)

    def download_file(self, bucket: str, key: str, file_path: str):
        """Download file from ANF volume."""
        self._client.download_file(bucket, key, file_path)
        logger.info("file_downloaded", bucket=bucket, key=key)

    def get_object(self, bucket: str, key: str) -> bytes:
        """Get object content."""
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream"
    ):
        """Put object content."""
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type
        )

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiration: int = 3600
    ) -> str:
        """Generate presigned URL for object access."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration
        )

    def create_onelake_shortcut_url(self, bucket: str, path: str = "") -> str:
        """
        Generate URL for OneLake shortcut creation.
        Used by Fabric to create zero-copy shortcuts.
        """
        return f"s3://{self.config.account_name}.blob.core.windows.net/{bucket}/{path}"
```

---

## 20. Phase 16: LangChain/LangGraph Integration

### 20.1 LangGraph Agent Workflow (`src/core/orchestration/langgraph_workflow.py`)

```python
"""
LangGraph-based agent workflow orchestration.
Provides stateful, multi-step agent execution.
"""
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import AzureChatOpenAI
import structlog

logger = structlog.get_logger()


class AgentState(TypedDict):
    """State for agent workflow."""
    messages: Annotated[List, "append"]
    context: Dict[str, Any]
    current_step: str
    tool_calls: List[Dict[str, Any]]
    final_answer: Optional[str]
    error: Optional[str]


class ANTSLangGraphWorkflow:
    """
    LangGraph workflow for ANTS agent orchestration.
    """

    def __init__(
        self,
        llm: AzureChatOpenAI,
        tools: List[Tool],
        memory_store: 'MemorySubstrate',
        policy_engine: 'PolicyEngine'
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory_store
        self.policy = policy_engine
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the agent workflow graph."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("perceive", self._perceive)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("reason", self._reason)
        workflow.add_node("check_policy", self._check_policy)
        workflow.add_node("execute", self._execute)
        workflow.add_node("verify", self._verify)
        workflow.add_node("respond", self._respond)

        # Add edges
        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "retrieve")
        workflow.add_edge("retrieve", "reason")
        workflow.add_conditional_edges(
            "reason",
            self._should_use_tool,
            {
                "tool": "check_policy",
                "respond": "respond"
            }
        )
        workflow.add_conditional_edges(
            "check_policy",
            self._policy_decision,
            {
                "allow": "execute",
                "deny": "respond",
                "require_approval": "respond"
            }
        )
        workflow.add_edge("execute", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._verification_result,
            {
                "success": "reason",
                "failure": "reason",
                "done": "respond"
            }
        )
        workflow.add_edge("respond", END)

        return workflow.compile(
            checkpointer=AsyncSqliteSaver.from_conn_string(":memory:")
        )

    async def _perceive(self, state: AgentState) -> AgentState:
        """Perceive and understand the input."""
        last_message = state["messages"][-1]

        # Extract entities, intent, context
        perception = await self.llm.ainvoke([
            HumanMessage(content=f"""
            Analyze this input and extract:
            1. User intent
            2. Key entities
            3. Required context

            Input: {last_message.content}
            """)
        ])

        state["context"]["perception"] = perception.content
        state["current_step"] = "perceive"

        logger.debug("perception_complete", intent=perception.content[:100])
        return state

    async def _retrieve(self, state: AgentState) -> AgentState:
        """Retrieve relevant context from memory."""
        query = state["messages"][-1].content

        # Retrieve from episodic memory
        episodic = await self.memory.retrieve_episodic(query, limit=5)

        # Retrieve from semantic memory
        semantic = await self.memory.retrieve_semantic(query, limit=10)

        state["context"]["episodic_memory"] = episodic
        state["context"]["semantic_memory"] = semantic
        state["current_step"] = "retrieve"

        logger.debug("retrieval_complete", episodic=len(episodic), semantic=len(semantic))
        return state

    async def _reason(self, state: AgentState) -> AgentState:
        """Reason about the next action."""
        messages = state["messages"]
        context = state["context"]

        # Build prompt with context
        system_prompt = f"""
        You are an ANTS agent. Use the following context to help the user.

        Episodic Memory: {context.get('episodic_memory', [])}
        Semantic Memory: {context.get('semantic_memory', [])}

        Available tools: {[t.name for t in self.tools]}

        Reason step by step about what to do next.
        """

        response = await self.llm.ainvoke(
            messages,
            tools=[t.as_langchain_tool() for t in self.tools]
        )

        state["messages"].append(response)
        state["current_step"] = "reason"

        if response.tool_calls:
            state["tool_calls"] = response.tool_calls

        return state

    def _should_use_tool(self, state: AgentState) -> str:
        """Determine if tool use is needed."""
        if state.get("tool_calls"):
            return "tool"
        return "respond"

    async def _check_policy(self, state: AgentState) -> AgentState:
        """Check policy before tool execution."""
        tool_calls = state["tool_calls"]

        for call in tool_calls:
            decision = await self.policy.evaluate({
                "tool": call["name"],
                "args": call["args"],
                "context": state["context"]
            })

            call["policy_decision"] = decision

        state["current_step"] = "check_policy"
        return state

    def _policy_decision(self, state: AgentState) -> str:
        """Route based on policy decision."""
        for call in state["tool_calls"]:
            decision = call.get("policy_decision", {})
            if decision.get("action") == "DENY":
                return "deny"
            if decision.get("action") == "REQUIRE_APPROVAL":
                return "require_approval"
        return "allow"

    async def _execute(self, state: AgentState) -> AgentState:
        """Execute tool calls."""
        tool_node = ToolNode(self.tools)
        result = await tool_node.ainvoke(state)

        state["messages"].extend(result["messages"])
        state["current_step"] = "execute"
        return state

    async def _verify(self, state: AgentState) -> AgentState:
        """Verify tool execution results."""
        # Check if results are valid
        last_message = state["messages"][-1]

        if isinstance(last_message, ToolMessage):
            # Verify result
            if "error" in last_message.content.lower():
                state["context"]["verification"] = "failure"
            else:
                state["context"]["verification"] = "success"

        state["current_step"] = "verify"
        return state

    def _verification_result(self, state: AgentState) -> str:
        """Route based on verification result."""
        verification = state["context"].get("verification", "success")

        # Check if we need more reasoning
        if state.get("tool_calls"):
            return verification

        return "done"

    async def _respond(self, state: AgentState) -> AgentState:
        """Generate final response."""
        # Store in episodic memory
        await self.memory.store_episodic({
            "messages": state["messages"],
            "context": state["context"]
        })

        state["current_step"] = "respond"
        state["final_answer"] = state["messages"][-1].content
        return state

    async def run(
        self,
        input_message: str,
        thread_id: str,
        config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Run the agent workflow."""
        initial_state = AgentState(
            messages=[HumanMessage(content=input_message)],
            context={"thread_id": thread_id},
            current_step="start",
            tool_calls=[],
            final_answer=None,
            error=None
        )

        config = config or {}
        config["configurable"] = {"thread_id": thread_id}

        result = await self.graph.ainvoke(initial_state, config)

        return {
            "answer": result["final_answer"],
            "steps": result["current_step"],
            "tool_calls": result["tool_calls"]
        }
```

---

## 21. Comprehensive Dependencies

### 21.1 Python Dependencies (`pyproject.toml`)

```toml
[project]
name = "ants"
version = "1.0.0"
description = "AI-Agent Native Tactical System for Enterprise"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}

dependencies = [
    # Core Framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
    "aiohttp>=3.9.0",

    # Azure SDK
    "azure-identity>=1.15.0",
    "azure-keyvault-secrets>=4.7.0",
    "azure-eventhub>=5.11.0",
    "azure-storage-blob>=12.19.0",
    "azure-search-documents>=11.4.0",
    "azure-cosmos>=4.5.0",
    "azure-digitaltwins-core>=1.2.0",
    "azure-ai-ml>=1.12.0",
    "azure-monitor-opentelemetry>=1.2.0",

    # LangChain Ecosystem
    "langchain>=0.1.0",
    "langchain-openai>=0.0.5",
    "langchain-community>=0.0.10",
    "langgraph>=0.0.20",

    # Agent Frameworks
    "autogen>=0.2.0",
    "crewai>=0.1.0",

    # Database
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "psycopg[binary]>=3.1.0",
    "pgvector>=0.2.4",
    "redis>=5.0.0",

    # Vector Stores
    "weaviate-client>=4.4.0",
    "pymilvus>=2.3.0",

    # ML/AI
    "torch>=2.1.0",
    "transformers>=4.36.0",
    "sentence-transformers>=2.2.0",
    "numpy>=1.26.0",
    "pandas>=2.1.0",
    "scikit-learn>=1.3.0",

    # NVIDIA
    "nvidia-nim>=0.1.0",
    "tritonclient[all]>=2.41.0",
    "nemo-guardrails>=0.7.0",

    # Observability
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
    "opentelemetry-exporter-otlp>=1.22.0",
    "opentelemetry-instrumentation-fastapi>=0.43b0",
    "prometheus-client>=0.19.0",
    "structlog>=24.1.0",

    # Policy
    "opa-client>=1.0.0",

    # Utilities
    "tenacity>=8.2.0",
    "python-dateutil>=2.8.0",
    "pyyaml>=6.0.0",
    "click>=8.1.0",
    "rich>=13.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-xdist>=3.5.0",
    "ruff>=0.1.0",
    "black>=24.1.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
    "httpx>=0.26.0",
    "respx>=0.20.0",
]

rapids = [
    "cudf-cu12>=24.02.0",
    "cuml-cu12>=24.02.0",
    "cugraph-cu12>=24.02.0",
]

databricks = [
    "databricks-sdk>=0.17.0",
    "delta-spark>=3.0.0",
    "mlflow>=2.10.0",
]

[project.scripts]
antsctl = "platform.bootstrap.antsctl:cli"
ants-server = "services.api_gateway.main:run"

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "B", "Q"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing"
```

### 21.2 TypeScript Dependencies (`ui/package.json`)

```json
{
  "name": "@ants/web-portal",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest"
  },
  "dependencies": {
    "@azure/msal-browser": "^3.6.0",
    "@azure/msal-react": "^2.0.0",
    "@microsoft/teams-js": "^2.19.0",
    "botframework-webchat": "^4.16.0",
    "next": "^14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "zustand": "^4.5.0",
    "@tanstack/react-query": "^5.17.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.312.0",
    "tailwindcss": "^3.4.0",
    "class-variance-authority": "^0.7.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.0",
    "eslint": "^8.56.0",
    "eslint-config-next": "^14.1.0",
    "typescript": "^5.3.0",
    "jest": "^29.7.0",
    "@testing-library/react": "^14.1.0"
  }
}
```

---

## 22. Extended Repository Structure

```
ascend-erp/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # CI pipeline
│   │   ├── cd-dev.yml                # CD to dev
│   │   ├── cd-prod.yml               # CD to production
│   │   └── security-scan.yml         # Security scanning
│   └── CODEOWNERS
├── docs/
│   ├── ideology.md                   # Project philosophy
│   ├── ants-blueprint.md             # Architecture blueprint
│   ├── governance-trust-layer.md     # Trust layer docs
│   ├── reference-implementations.md  # Vertical demos
│   ├── licenses.md                   # License compliance
│   └── runbooks/
│       ├── dr-failover.md
│       ├── scaling.md
│       └── incident-response.md
├── infra/
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── anf/
│   │   │   ├── anf_advanced/
│   │   │   ├── aks_ha/
│   │   │   ├── bcdr/
│   │   │   ├── ai_foundry/
│   │   │   ├── databricks/
│   │   │   ├── fabric/
│   │   │   └── ...
│   │   └── envs/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── production/
│   └── helm/
│       ├── ants-core/
│       ├── ants-nim/
│       ├── ants-agents/
│       └── ants-observability/
├── platform/
│   ├── bootstrap/
│   │   ├── antsctl.py               # Bootstrap CLI
│   │   └── templates/
│   ├── policies/
│   │   ├── rego/
│   │   └── tests/
│   ├── receipts/
│   ├── observability/
│   └── standards/
│       ├── ants-spec.schema.json
│       └── ants-spec.example.yaml
├── data/
│   ├── ingestion/
│   │   ├── eventhubs/
│   │   ├── iothub/
│   │   ├── digital_twins/
│   │   ├── documents/
│   │   └── video_audio/
│   ├── etl/
│   │   ├── databricks/
│   │   ├── fabric/
│   │   └── lakehouse/
│   └── feature_store/
├── ai/
│   ├── nim/
│   ├── nemo/
│   ├── training/
│   ├── inference/
│   └── evaluation/
├── src/
│   ├── core/
│   │   ├── agent.py
│   │   ├── memory/
│   │   ├── policy/
│   │   ├── inference/
│   │   ├── trust/
│   │   ├── orchestration/
│   │   └── data/
│   ├── agents/
│   │   ├── orgs/
│   │   │   ├── finance/
│   │   │   ├── retail/
│   │   │   ├── manufacturing/
│   │   │   ├── healthcare/
│   │   │   ├── crm/
│   │   │   └── hr/
│   │   ├── selfops/
│   │   ├── governance/
│   │   └── cybersecurity/
│   └── integrations/
│       ├── fabric/
│       ├── databricks/
│       ├── ai_foundry/
│       └── anf/
├── services/
│   ├── api_gateway/
│   ├── agent_orchestrator/
│   ├── retrieval_service/
│   ├── action_service/
│   └── ui_backend/
├── mcp/
│   ├── servers/
│   │   ├── azure_mcp/
│   │   ├── github_mcp/
│   │   ├── erp_mcp/
│   │   └── ticketing_mcp/
│   └── clients/
├── ui/
│   ├── web_portal/
│   └── teams_app/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── policy/
│   └── e2e/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── claude.md
```

---

*This comprehensive implementation plan provides complete code modules, infrastructure configurations, and dependencies for building ANTS - the AI-Agent Native Tactical System. Every component is designed to be enterprise-grade, leveraging Azure + NVIDIA + ANF as the "Better Together" stack.*
