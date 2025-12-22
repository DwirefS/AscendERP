# ANTS/Ascend ERP: Code Modules Planning
**Comprehensive Module Architecture and Implementation Guide**

---

## 1. REPOSITORY STRUCTURE OVERVIEW

```
ascend-erp/
├── 📁 docs/                           # Documentation and specifications
│   ├── architecture/                  # Architecture decision records
│   ├── api/                          # API specifications (OpenAPI)
│   ├── whitepaper/                   # Technical white paper content
│   └── blog/                         # Blog post drafts
│
├── 📁 infra/                          # Infrastructure as Code
│   ├── terraform/                    # Azure infrastructure
│   │   ├── modules/                  # Reusable Terraform modules
│   │   ├── environments/             # Dev, staging, prod configs
│   │   └── main.tf                   # Root orchestration
│   ├── helm/                         # Kubernetes deployments
│   │   ├── ants-core/               # Core ANTS services
│   │   ├── agents/                  # Agent deployments
│   │   └── observability/           # Monitoring stack
│   └── ansible/                      # Configuration management
│
├── 📁 src/                            # Source code
│   ├── core/                         # Core ANTS framework
│   ├── agents/                       # Agent implementations
│   ├── memory/                       # Memory substrate layer
│   ├── governance/                   # Trust and policy layer
│   ├── selfops/                      # SelfOps agent teams
│   ├── integrations/                 # External integrations
│   └── api/                          # API gateway
│
├── 📁 reference-implementations/      # Vertical demos
│   ├── common/                       # Shared components
│   ├── finance/                      # Finance vertical
│   ├── retail/                       # Retail vertical
│   ├── healthcare/                   # Healthcare vertical
│   └── manufacturing/                # Manufacturing vertical
│
├── 📁 tests/                          # Test suites
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   ├── e2e/                          # End-to-end tests
│   └── eval/                         # CLEAR metrics evaluation
│
├── 📁 scripts/                        # Utility scripts
│   ├── setup/                        # Environment setup
│   ├── data/                         # Data loading
│   └── demo/                         # Demo runners
│
└── 📁 .github/                        # GitHub workflows
    ├── workflows/                    # CI/CD pipelines
    └── ISSUE_TEMPLATE/               # Issue templates
```

---

## 2. CORE FRAMEWORK MODULES

### 2.1 Module: `src/core/`
**Purpose**: The foundational ANTS framework that all other components build upon.

```
src/core/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py              # Application settings (pydantic)
│   └── constants.py             # System constants
├── models/
│   ├── __init__.py
│   ├── agent.py                 # Agent base models
│   ├── action.py                # Action envelope models
│   ├── receipt.py               # Audit receipt models
│   ├── memory.py                # Memory type models
│   └── policy.py                # Policy decision models
├── protocols/
│   ├── __init__.py
│   ├── mcp/                     # Model Context Protocol
│   │   ├── __init__.py
│   │   ├── server.py            # MCP server implementation
│   │   ├── tools.py             # Tool definitions
│   │   └── resources.py         # Resource handlers
│   └── a2a/                     # Agent-to-Agent Protocol
│       ├── __init__.py
│       ├── client.py            # A2A client
│       └── server.py            # A2A server
├── utils/
│   ├── __init__.py
│   ├── logging.py               # Structured logging
│   ├── telemetry.py             # OpenTelemetry integration
│   └── serialization.py         # JSON/YAML utilities
└── exceptions.py                # Custom exception classes
```

**Key Implementation Files**:

```python
# src/core/models/action.py
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    QUARANTINE_AGENT = "QUARANTINE_AGENT"

class PolicyContext(BaseModel):
    role: str
    data_class: List[str]
    environment: str

class ModelInfo(BaseModel):
    name: str
    version: str

class ActionEnvelope(BaseModel):
    """Standard envelope for all agent actions (per Governance spec)."""
    trace_id: str
    tenant_id: str
    user_id: str
    agent_id: str
    policy_context: PolicyContext
    intent: str
    tool: str
    args: Dict
    model: ModelInfo
    artifacts: Dict[str, List[str]]
    timestamp: datetime = datetime.utcnow()
```

---

### 2.2 Module: `src/agents/`
**Purpose**: Agent persona implementations using LangChain/LangGraph/AutoGen.

```
src/agents/
├── __init__.py
├── base/
│   ├── __init__.py
│   ├── agent.py                 # Base agent class
│   ├── memory.py                # Agent memory management
│   ├── tools.py                 # Base tool registry
│   └── reasoning.py             # Reasoning patterns
├── orchestrator/
│   ├── __init__.py
│   ├── coordinator.py           # Multi-agent coordinator
│   ├── workflow.py              # LangGraph workflow definitions
│   └── scheduler.py             # Task scheduling
├── finance/
│   ├── __init__.py
│   ├── reconciliation.py        # Reconciliation agent
│   ├── ap_automation.py         # Accounts payable agent
│   ├── ar_automation.py         # Accounts receivable agent
│   └── forecasting.py           # Financial forecasting agent
├── supplychain/
│   ├── __init__.py
│   ├── demand_forecast.py       # Demand forecasting agent
│   ├── inventory.py             # Inventory management agent
│   └── procurement.py           # Procurement agent
├── hr/
│   ├── __init__.py
│   ├── onboarding.py            # Onboarding workflow agent
│   ├── support.py               # HR support agent
│   └── analytics.py             # HR analytics agent
└── crm/
    ├── __init__.py
    ├── customer_service.py      # Customer service agent
    ├── sales_assistant.py       # Sales assistant agent
    └── marketing.py             # Marketing insights agent
```

**Key Implementation Pattern**:

```python
# src/agents/base/agent.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor
from langgraph.graph import StateGraph

from src.core.models.action import ActionEnvelope, PolicyDecision
from src.governance.policy import PolicyEngine
from src.memory.manager import MemoryManager

class ANTSAgent(ABC):
    """Base class for all ANTS agents."""
    
    def __init__(
        self,
        agent_id: str,
        model_name: str,
        tools: List[BaseTool],
        policy_engine: PolicyEngine,
        memory_manager: MemoryManager,
    ):
        self.agent_id = agent_id
        self.model_name = model_name
        self.tools = tools
        self.policy_engine = policy_engine
        self.memory_manager = memory_manager
        
    @abstractmethod
    async def perceive(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perceive and process input data."""
        pass
    
    @abstractmethod
    async def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant context from memory."""
        pass
    
    @abstractmethod
    async def reason(self, context: Dict[str, Any]) -> ActionEnvelope:
        """Reason about action to take."""
        pass
    
    async def execute(self, action: ActionEnvelope) -> Dict[str, Any]:
        """Execute action with policy gating."""
        # Policy check
        decision = await self.policy_engine.evaluate(action)
        
        if decision == PolicyDecision.DENY:
            return {"status": "denied", "reason": "Policy violation"}
        
        if decision == PolicyDecision.REQUIRE_APPROVAL:
            return await self._request_human_approval(action)
        
        # Execute the action
        result = await self._execute_action(action)
        
        # Record receipt
        await self.memory_manager.record_receipt(action, result)
        
        return result
    
    async def learn(self, feedback: Dict[str, Any]) -> None:
        """Learn from feedback and update memory."""
        await self.memory_manager.update_episodic(feedback)
```

---

### 2.3 Module: `src/memory/`
**Purpose**: Memory substrate implementation (episodic, semantic, procedural, model).

```
src/memory/
├── __init__.py
├── manager.py                   # Unified memory manager
├── types/
│   ├── __init__.py
│   ├── episodic.py             # Episodic memory (traces, receipts)
│   ├── semantic.py             # Semantic memory (vectors, embeddings)
│   ├── procedural.py           # Procedural memory (runbooks, policies)
│   └── model.py                # Model memory (checkpoints, weights)
├── stores/
│   ├── __init__.py
│   ├── postgresql.py           # PostgreSQL + pgvector
│   ├── weaviate.py             # Weaviate vector store
│   ├── milvus.py               # Milvus vector store
│   └── anf.py                  # ANF file storage
├── entropy/
│   ├── __init__.py
│   ├── aging.py                # Memory aging policies
│   ├── decay.py                # Decay rules (forget/summarize/compress)
│   └── retention.py            # Retention SLAs
└── embedding/
    ├── __init__.py
    ├── nvidia_nim.py           # NVIDIA NIM embeddings
    └── chunking.py             # Document chunking strategies
```

**Key Implementation Pattern**:

```python
# src/memory/manager.py
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.memory.types import EpisodicMemory, SemanticMemory, ProceduralMemory, ModelMemory
from src.memory.stores import PostgreSQLStore, VectorStore, ANFStore
from src.memory.entropy import AgingPolicy, DecayRule

class MemoryManager:
    """Unified interface to the memory substrate."""
    
    def __init__(
        self,
        pg_connection: str,
        vector_store: VectorStore,
        anf_mount: str,
        aging_policy: AgingPolicy,
    ):
        self.episodic = EpisodicMemory(PostgreSQLStore(pg_connection))
        self.semantic = SemanticMemory(vector_store)
        self.procedural = ProceduralMemory(ANFStore(anf_mount, "procedural"))
        self.model = ModelMemory(ANFStore(anf_mount, "models"))
        self.aging_policy = aging_policy
        
    async def record_receipt(
        self,
        action: ActionEnvelope,
        result: Dict[str, Any],
    ) -> str:
        """Record an audit receipt (episodic memory)."""
        receipt = AuditReceipt(
            trace_id=action.trace_id,
            timestamp=datetime.utcnow(),
            actor=ActorInfo(user_id=action.user_id, agent_id=action.agent_id),
            action=ActionInfo(tool=action.tool, args_hash=hash_dict(action.args)),
            result=result,
        )
        return await self.episodic.store(receipt)
    
    async def retrieve_context(
        self,
        query: str,
        top_k: int = 10,
        memory_types: List[str] = ["semantic", "episodic"],
    ) -> List[MemoryItem]:
        """Retrieve relevant context from multiple memory types."""
        results = []
        
        if "semantic" in memory_types:
            results.extend(await self.semantic.search(query, top_k))
        
        if "episodic" in memory_types:
            results.extend(await self.episodic.search(query, top_k))
        
        if "procedural" in memory_types:
            results.extend(await self.procedural.search(query, top_k))
        
        # Rank and deduplicate
        return self._rank_and_dedupe(results, top_k)
    
    async def apply_entropy(self) -> EntropyReport:
        """Apply aging and decay policies to memory."""
        report = EntropyReport()
        
        # Age out old episodic memories
        aged = await self.episodic.age_out(self.aging_policy.episodic_ttl)
        report.episodic_aged = aged
        
        # Compress old semantic memories
        compressed = await self.semantic.compress(self.aging_policy.semantic_ttl)
        report.semantic_compressed = compressed
        
        return report
```

---

### 2.4 Module: `src/governance/`
**Purpose**: Trust layer implementation (policy-as-code, audit, security).

```
src/governance/
├── __init__.py
├── policy/
│   ├── __init__.py
│   ├── engine.py               # OPA policy engine wrapper
│   ├── loader.py               # Policy file loader
│   └── models.py               # Policy models
├── audit/
│   ├── __init__.py
│   ├── receipts.py             # Audit receipt management
│   ├── storage.py              # Receipt storage (PG + ANF)
│   └── query.py                # Audit query interface
├── hitl/
│   ├── __init__.py
│   ├── approval.py             # Human approval workflow
│   ├── notification.py         # Teams/email notification
│   └── ui.py                   # Approval UI components
├── security/
│   ├── __init__.py
│   ├── identity.py             # Service principal management
│   ├── quarantine.py           # Agent quarantine logic
│   └── segmentation.py         # Namespace segmentation
├── clear/
│   ├── __init__.py
│   ├── metrics.py              # CLEAR metrics calculation
│   ├── collector.py            # Metrics collection
│   └── thresholds.py           # Alert thresholds
└── rego/                       # OPA Rego policies
    ├── common/
    │   ├── base.rego           # Base policy rules
    │   └── roles.rego          # Role definitions
    ├── finance/
    │   ├── sox_gate.rego       # SOX compliance gates
    │   └── approval.rego       # Approval thresholds
    ├── healthcare/
    │   ├── hipaa_access.rego   # HIPAA access controls
    │   └── phi_redaction.rego  # PHI redaction rules
    └── retail/
        └── pci.rego            # PCI-DSS requirements
```

**Key Implementation Pattern**:

```python
# src/governance/policy/engine.py
import httpx
from typing import Dict, Any

from src.core.models.action import ActionEnvelope, PolicyDecision

class PolicyEngine:
    """OPA-based policy engine for action gating."""
    
    def __init__(self, opa_url: str = "http://opa:8181"):
        self.opa_url = opa_url
        self.client = httpx.AsyncClient()
        
    async def evaluate(self, action: ActionEnvelope) -> PolicyDecision:
        """Evaluate action against policies."""
        input_data = {
            "input": {
                "agent_id": action.agent_id,
                "intent": action.intent,
                "tool": action.tool,
                "args": action.args,
                "context": action.policy_context.dict(),
            }
        }
        
        response = await self.client.post(
            f"{self.opa_url}/v1/data/ants/action/decision",
            json=input_data,
        )
        
        result = response.json()
        decision = result.get("result", {}).get("decision", "DENY")
        
        return PolicyDecision(decision)
    
    async def get_required_approvers(self, action: ActionEnvelope) -> List[str]:
        """Get list of required approvers for an action."""
        response = await self.client.post(
            f"{self.opa_url}/v1/data/ants/approval/approvers",
            json={"input": action.dict()},
        )
        return response.json().get("result", [])
```

---

### 2.5 Module: `src/selfops/`
**Purpose**: SelfOps agent teams for autonomous operations.

```
src/selfops/
├── __init__.py
├── teams/
│   ├── __init__.py
│   ├── infraops.py             # Infrastructure operations
│   │   ├── scaling.py          # Auto-scaling logic
│   │   ├── patching.py         # Security patching
│   │   └── cost_optimizer.py   # Cost optimization
│   ├── dataops.py              # Data operations
│   │   ├── ingestion.py        # Ingestion health
│   │   ├── schema_evolution.py # Schema management
│   │   └── indexing.py         # Index maintenance
│   ├── agentops.py             # Agent operations
│   │   ├── drift_detection.py  # Model/prompt drift
│   │   ├── prompt_testing.py   # Prompt evaluation
│   │   └── canary.py           # Canary deployments
│   └── secops.py               # Security operations
│       ├── anomaly.py          # Anomaly detection
│       ├── policy_enforce.py   # Policy enforcement
│       └── quarantine.py       # Agent quarantine
├── workflows/
│   ├── __init__.py
│   ├── remediation.py          # Auto-remediation workflows
│   ├── rollback.py             # Rollback procedures
│   └── snapshot.py             # Snapshot management
├── monitoring/
│   ├── __init__.py
│   ├── health.py               # Health checks
│   ├── drift.py                # Drift metrics
│   └── alerts.py               # Alert management
└── tools/
    ├── __init__.py
    ├── azure.py                # Azure management tools
    ├── kubernetes.py           # K8s management tools
    └── anf.py                  # ANF snapshot tools
```

**Key Implementation Pattern**:

```python
# src/selfops/teams/agentops.py
from typing import Dict, List, Any
from datetime import datetime, timedelta

from src.selfops.monitoring import DriftMetrics
from src.selfops.workflows import RollbackWorkflow
from src.memory.manager import MemoryManager

class AgentOpsTeam:
    """SelfOps team for agent lifecycle management."""
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        drift_threshold: float = 0.1,
    ):
        self.memory = memory_manager
        self.drift_threshold = drift_threshold
        self.drift_metrics = DriftMetrics()
        
    async def detect_drift(self, agent_id: str) -> DriftReport:
        """Detect prompt or model drift for an agent."""
        # Get recent performance metrics
        recent = await self._get_recent_metrics(agent_id, hours=24)
        baseline = await self._get_baseline_metrics(agent_id)
        
        # Calculate drift
        prompt_drift = self._calculate_drift(recent.prompt_success, baseline.prompt_success)
        embedding_drift = self._calculate_drift(recent.embedding_quality, baseline.embedding_quality)
        retrieval_drift = self._calculate_drift(recent.retrieval_accuracy, baseline.retrieval_accuracy)
        
        report = DriftReport(
            agent_id=agent_id,
            timestamp=datetime.utcnow(),
            prompt_drift=prompt_drift,
            embedding_drift=embedding_drift,
            retrieval_drift=retrieval_drift,
            requires_action=any([
                prompt_drift > self.drift_threshold,
                embedding_drift > self.drift_threshold,
                retrieval_drift > self.drift_threshold,
            ]),
        )
        
        if report.requires_action:
            await self._trigger_remediation(report)
        
        return report
    
    async def _trigger_remediation(self, report: DriftReport) -> None:
        """Trigger auto-remediation based on drift report."""
        if report.prompt_drift > self.drift_threshold:
            await RollbackWorkflow.rollback_prompt(report.agent_id)
        
        if report.embedding_drift > self.drift_threshold:
            await RollbackWorkflow.reindex_embeddings(report.agent_id)
        
        if report.retrieval_drift > self.drift_threshold:
            await RollbackWorkflow.restore_index_snapshot(report.agent_id)
```

---

## 3. INFRASTRUCTURE MODULES

### 3.1 Terraform Module Structure

```
infra/terraform/
├── main.tf                      # Root module
├── variables.tf                 # Input variables
├── outputs.tf                   # Output values
├── providers.tf                 # Provider configuration
├── versions.tf                  # Version constraints
│
├── modules/
│   ├── networking/              # VNet, subnets, NSGs
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── aks/                     # Azure Kubernetes Service
│   │   ├── main.tf              # AKS cluster
│   │   ├── gpu_nodepool.tf      # GPU node pools
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── anf/                     # Azure NetApp Files
│   │   ├── main.tf              # ANF account
│   │   ├── pools.tf             # Capacity pools (Ultra/Premium/Standard)
│   │   ├── volumes.tf           # Volumes configuration
│   │   ├── snapshots.tf         # Snapshot policies
│   │   ├── replication.tf       # Cross-region replication
│   │   └── object_api.tf        # Object REST API config
│   │
│   ├── postgresql/              # PostgreSQL + pgvector
│   │   ├── main.tf
│   │   ├── extensions.tf        # pgvector extension
│   │   └── backup.tf
│   │
│   ├── nvidia/                  # NVIDIA NIM deployment
│   │   ├── main.tf              # Container Apps with GPU
│   │   ├── nim_endpoints.tf     # NIM model endpoints
│   │   └── triton.tf            # Triton server config
│   │
│   ├── ai_services/             # Azure AI services
│   │   ├── ai_foundry.tf        # AI Foundry
│   │   ├── ai_search.tf         # AI Search
│   │   └── openai.tf            # Azure OpenAI
│   │
│   ├── governance/              # Governance infrastructure
│   │   ├── opa.tf               # OPA server deployment
│   │   ├── keyvault.tf          # Secret management
│   │   └── monitoring.tf        # Azure Monitor
│   │
│   └── bcdr/                    # BCDR infrastructure
│       ├── backup.tf            # Backup configuration
│       ├── replication.tf       # Geo-replication
│       └── failover.tf          # Failover setup
│
└── environments/
    ├── dev/
    │   ├── main.tf
    │   └── terraform.tfvars
    ├── staging/
    │   ├── main.tf
    │   └── terraform.tfvars
    └── prod/
        ├── main.tf
        └── terraform.tfvars
```

### 3.2 Helm Chart Structure

```
infra/helm/
├── ants-core/                   # Core ANTS services
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── templates/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml
│   │   └── pvc.yaml            # ANF persistent volumes
│   └── charts/
│       └── memory-manager/
│
├── agents/                      # Agent deployments
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── finance-agent.yaml
│       ├── supplychain-agent.yaml
│       ├── hr-agent.yaml
│       └── crm-agent.yaml
│
├── selfops/                     # SelfOps services
│   ├── Chart.yaml
│   └── templates/
│       ├── infraops.yaml
│       ├── dataops.yaml
│       ├── agentops.yaml
│       └── secops.yaml
│
└── observability/               # Monitoring stack
    ├── Chart.yaml
    └── templates/
        ├── prometheus.yaml
        ├── grafana.yaml
        ├── otel-collector.yaml
        └── dashboards/
```

---

## 4. REFERENCE IMPLEMENTATION MODULES

### 4.1 Common Shared Components

```
reference-implementations/common/
├── datasets/                    # Sample data
│   ├── README.md               # Data provenance documentation
│   ├── synthetic/              # Generated synthetic data
│   │   ├── invoices/
│   │   ├── purchase_orders/
│   │   └── transactions/
│   └── scripts/
│       ├── generate.py         # Data generation scripts
│       └── validate.py         # Data validation
│
├── scripts/                     # Utility scripts
│   ├── load_data.py            # Load sample data
│   ├── seed_db.py              # Database seeding
│   └── run_demo.py             # Demo runner
│
├── eval/                        # Evaluation harness
│   ├── clear_metrics.py        # CLEAR metrics calculator
│   ├── rag_eval.py             # RAG evaluation (RAGAS)
│   ├── accuracy_suite.py       # Accuracy testing
│   └── benchmark.py            # Performance benchmarks
│
├── mcp/                         # MCP tool servers
│   ├── github_stub/            # GitHub integration stub
│   ├── itops_stub/             # ITOps integration stub
│   ├── ticketing_stub/         # Ticketing system stub
│   └── erp_stub/               # ERP integration stub
│
├── policies/                    # Common OPA policies
│   ├── base.rego               # Base policy rules
│   ├── roles.rego              # Role definitions
│   └── data_classification.rego
│
└── dashboards/                  # Starter dashboards
    ├── grafana/                # Grafana JSON definitions
    └── powerbi/                # Power BI templates
```

### 4.2 Finance Vertical

```
reference-implementations/finance/
├── README.md                    # Demo narrative and instructions
├── demo.md                      # Step-by-step demo guide
│
├── src/
│   ├── agents/
│   │   ├── finance_recon_agent.py    # Reconciliation agent
│   │   ├── ap_agent.py               # Accounts payable
│   │   └── ar_agent.py               # Accounts receivable
│   ├── tools/
│   │   ├── erp_connector.py          # ERP integration tools
│   │   ├── gl_query.py               # GL query tools
│   │   └── matching.py               # PO/Invoice matching
│   └── workflows/
│       ├── month_end_close.py        # Month-end workflow
│       └── exception_handling.py     # Exception workflows
│
├── policies/
│   ├── sox_gate.rego                 # SOX compliance gates
│   └── approval_thresholds.rego      # Approval limits
│
├── data/
│   ├── sample_invoices/              # Sample invoice PDFs
│   ├── sample_pos/                   # Sample purchase orders
│   └── sample_gl/                    # Sample GL entries
│
├── eval/
│   ├── accuracy_suite.py             # Reconciliation accuracy
│   └── compliance_check.py           # SOX compliance tests
│
└── deploy/
    ├── helm/                         # Helm chart overrides
    └── scripts/
        ├── load_data.py
        └── run_demo.sh
```

### 4.3 Retail Vertical

```
reference-implementations/retail/
├── README.md
├── demo.md
│
├── src/
│   ├── agents/
│   │   ├── demand_forecast_agent.py  # Demand forecasting
│   │   ├── inventory_agent.py        # Inventory management
│   │   └── replenishment_agent.py    # Auto-replenishment
│   ├── tools/
│   │   ├── pos_connector.py          # POS data connector
│   │   ├── inventory_query.py        # Inventory queries
│   │   └── supplier_api.py           # Supplier integration
│   └── workflows/
│       ├── demand_to_order.py        # Demand → PO workflow
│       └── markdown_decision.py      # Markdown optimization
│
├── streaming/
│   ├── pos_simulator.py              # POS event simulator
│   ├── event_processor.py            # Event Hubs processor
│   └── aggregation.py                # Real-time aggregation
│
├── policies/
│   ├── reorder_limits.rego           # Reorder constraints
│   └── pci_compliance.rego           # PCI-DSS rules
│
├── dashboards/
│   ├── demand_forecast.json          # Forecast dashboard
│   └── inventory_health.json         # Inventory dashboard
│
└── deploy/
    ├── helm/
    └── scripts/
```

### 4.4 Healthcare Vertical

```
reference-implementations/healthcare/
├── README.md
├── demo.md
│
├── src/
│   ├── agents/
│   │   ├── clinical_rag_agent.py     # PHI-safe RAG
│   │   ├── revenue_cycle_agent.py    # Revenue cycle
│   │   └── coding_agent.py           # Medical coding assist
│   ├── tools/
│   │   ├── fhir_connector.py         # FHIR API connector
│   │   ├── coding_lookup.py          # ICD/CPT lookup
│   │   └── phi_detector.py           # PHI detection
│   └── workflows/
│       ├── claim_submission.py       # Claim workflow
│       └── prior_auth.py             # Prior authorization
│
├── middleware/
│   ├── redaction_middleware.py       # PHI redaction
│   ├── access_control.py             # Role-based access
│   └── audit_logger.py               # HIPAA audit logging
│
├── policies/
│   ├── hipaa_access.rego             # HIPAA access control
│   ├── phi_redaction.rego            # PHI handling rules
│   └── audit_retention.rego          # Audit retention policy
│
├── data/
│   ├── synthetic_notes/              # Synthetic clinical notes
│   └── sample_claims/                # Sample claims data
│
└── deploy/
    ├── helm/
    └── scripts/
```

### 4.5 Manufacturing Vertical

```
reference-implementations/manufacturing/
├── README.md
├── demo.md
│
├── src/
│   ├── agents/
│   │   ├── maintenance_agent.py      # Predictive maintenance
│   │   ├── quality_agent.py          # Quality control
│   │   └── twin_agent.py             # Digital twin manager
│   ├── tools/
│   │   ├── iot_connector.py          # IoT Hub connector
│   │   ├── twin_query.py             # Digital Twin queries
│   │   └── work_order.py             # Work order creation
│   └── workflows/
│       ├── maintenance_workflow.py   # Maintenance automation
│       └── quality_inspection.py     # QA workflow
│
├── digital_twin/
│   ├── twin_event_router.py          # Event routing
│   ├── twin_sync.py                  # State synchronization
│   └── twin_models/                  # Twin model definitions
│
├── vision/
│   ├── quality_inspection.py         # Vision QA model
│   ├── video_summarization.py        # VSS integration
│   └── anomaly_detection.py          # Visual anomaly detection
│
├── policies/
│   ├── safety_constraints.rego       # Safety rules
│   └── maintenance_approval.rego     # Maintenance gates
│
└── deploy/
    ├── helm/
    └── scripts/
```

---

## 5. DEVELOPMENT PRIORITIES

### Phase 1: Foundation (Weeks 1-4)
1. Set up repository structure
2. Implement `src/core/` models and utilities
3. Create Terraform modules for base infrastructure
4. Deploy ANF volumes and PostgreSQL
5. Basic LangChain agent skeleton

### Phase 2: Memory & Governance (Weeks 5-8)
1. Implement `src/memory/` with PostgreSQL + pgvector
2. Implement `src/governance/` with OPA integration
3. Create base policies in Rego
4. Deploy NIM containers for inference
5. Basic audit receipt logging

### Phase 3: Agents (Weeks 9-12)
1. Implement base agent class
2. Create Finance reconciliation agent
3. Create Supply Chain demand agent
4. Multi-agent orchestration with LangGraph
5. MCP tool server implementations

### Phase 4: SelfOps (Weeks 13-16)
1. Implement `src/selfops/` teams
2. Drift detection and alerting
3. Auto-remediation workflows
4. Snapshot-based rollback
5. CLEAR metrics dashboard

### Phase 5: Verticals & Polish (Weeks 17-20)
1. Complete all four vertical demos
2. End-to-end testing
3. Documentation and white paper
4. Performance optimization
5. Security hardening

---

*This code modules plan provides the complete blueprint for implementing ANTS/Ascend ERP. Each module is designed to be independently testable while contributing to the unified vision.*
