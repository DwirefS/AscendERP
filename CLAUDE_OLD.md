# Ascend EOS / ANTS Project - Claude Code Instructions

## Project Overview

**Ascend EOS** (Enterprise Operating System) / **ANTS** (AI-Agent Native Tactical System) is an enterprise-grade AI agent platform that reimagines enterprise software through the lens of agentic AI. The platform treats the enterprise as a "digital organism" where specialized AI agents (cells) work together in organ systems (departments) to achieve collective intelligence.

## Core Philosophy

1. **Digital Organism Metaphor**: Enterprise as a living system with specialized agents as cells
2. **"Better Together" Stack**: Azure + NVIDIA + Azure NetApp Files as the foundation
3. **Zero-Copy Architecture**: Memory substrate that eliminates data movement
4. **Policy-Governed Autonomy**: All agent actions pass through policy gates with audit receipts
5. **SelfOps**: Self-managing infrastructure through specialized agent teams

## Key Principles (NO DELETIONS)

- **Always enrichment, never deletion** - Add to existing content, don't remove
- **Positive framing** - Describe opportunities, not problems
- **Nature-inspired patterns** - Map biological patterns to architecture
- **Musical composition metaphor** - Cloud components as instruments, architecture as symphony
- **Brand-agnostic artistry** - Reference technologies by function, not endorsement

## Technology Stack

### Azure Services
- AKS (Kubernetes), Container Apps
- Azure NetApp Files (Memory Substrate)
- Azure AI Foundry, AI Search
- Databricks, Fabric/OneLake
- Event Hubs, IoT Hub, Digital Twins
- PostgreSQL Flexible Server + pgvector

### NVIDIA Stack
- NIM (Inference Microservices)
- Nemotron models (Nano, Super, Ultra)
- NeMo Framework & Guardrails
- RAPIDS (GPU-accelerated data processing)
- Triton Inference Server

### ANF Features
- Ultra/Premium/Standard service levels
- Cool access tier for archival
- Object REST API (S3-compatible)
- Cross-region replication
- Snapshots and clones

### Agent Frameworks
- LangChain / LangGraph
- AutoGen
- CrewAI
- MCP (Model Context Protocol)
- A2A (Agent-to-Agent)

## Repository Structure

```
ascend-erp/
├── docs/                    # Documentation
├── infra/                   # Infrastructure as Code
│   ├── terraform/
│   └── helm/
├── platform/                # Platform services
│   ├── bootstrap/           # antsctl CLI
│   ├── policies/            # OPA/Rego
│   └── receipts/            # Audit receipts
├── data/                    # Data pipelines
│   ├── ingestion/
│   └── etl/
├── ai/                      # AI/ML components
│   ├── nim/
│   └── nemo/
├── src/                     # Source code
│   ├── core/                # Core framework
│   ├── agents/              # Agent implementations
│   └── integrations/        # External integrations
├── services/                # Microservices
├── mcp/                     # MCP servers
├── ui/                      # User interfaces
└── tests/                   # Test suites
```

## Agent Types

### Business Organs
- **Finance**: Reconciliation, AP/AR, Close & Reporting
- **Retail**: Demand Signals, Inventory, Customer Support
- **Manufacturing**: Digital Twin, Predictive Maintenance, Quality
- **Healthcare**: PHI-safe RAG, Revenue Cycle, Coding
- **CRM**: Lead Qualification, Account Insights
- **HR**: Onboarding, Policy Q&A

### Platform Organs
- **Governance**: Policy, Compliance, Audit
- **Cybersecurity**: Defender Triage, Sentinel Investigation
- **SelfOps**: InfraOps, DataOps, AgentOps, SecOps

## Key Files

- `plan.md` - Comprehensive implementation blueprint
- `ASCEND_EOS_WHITEPAPER_FINAL.md` - White paper
- `seed/` - All seed context files
- `work-log/WORK_LOG.md` - Development progress log

## Development Guidelines

### Code Style
- Python 3.11+ with type hints
- FastAPI for APIs
- Async/await patterns
- Structured logging (structlog)
- Pydantic for validation

### Infrastructure
- Terraform for Azure resources
- Helm charts for Kubernetes
- Policy-as-code with OPA/Rego

### Testing
- pytest for unit tests
- pytest-asyncio for async tests
- Integration tests for services
- Policy tests for OPA rules

## Memory Types

1. **Episodic**: Agent execution traces
2. **Semantic**: Vector embeddings for RAG
3. **Procedural**: Successful action patterns
4. **Model**: Active model weights/adapters

## CLEAR Metrics

- **C**ost: Token usage, GPU seconds, estimated cost
- **L**atency: P50, P95, P99 response times
- **E**fficacy: Success rate, confidence scores
- **A**ssurance: Policy compliance, audit coverage
- **R**eliability: Error rates, availability

## Useful Commands

```bash
# Bootstrap deployment
antsctl deploy --spec ants-spec.yaml

# Validate spec
antsctl validate --spec ants-spec.yaml

# Run tests
pytest tests/ -v

# Lint code
ruff check src/
black src/ --check

# Type checking
mypy src/
```

## Important Notes

1. Always check policy before agent actions
2. Generate audit receipts for all tool executions
3. Use ANF for all persistent memory storage
4. Prefer NIM for inference (2.6x throughput improvement)
5. Enable cool access tier for archival data
6. Use OneLake shortcuts for zero-copy analytics
