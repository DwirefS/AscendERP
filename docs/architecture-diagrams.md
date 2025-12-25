# ANTS Architecture Diagrams

Professional architecture diagrams for ANTS platform.

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph "User Layer"
        UI[Web Portal]
        Teams[Microsoft Teams]
        API[REST API]
    end

    subgraph "AG-UI Streaming Layer"
        SSE[Server-Sent Events]
        WS[WebSocket Streams]
        DevUI[DevUI Dashboard]
    end

    subgraph "ANTS Core - Biological Intelligence Patterns"
        subgraph "Decision Councils"
            Council[5-Phase Deliberation]
            Consensus[Consensus Engine]
            Vote[Weighted Voting]
        end

        subgraph "Swarm Coordination"
            Pheromone[Pheromone Trails]
            EventHub[Event Hubs]
            Emergence[Emergent Behavior]
        end

        subgraph "Polymorphic Agents"
            Stem[Stem Cell Agents]
            Diff[Differentiation]
            Spec[Specialized Agents]
        end

        subgraph "Meta-Agents"
            CodeGen[Code Generator]
            IntGen[Integration Builder]
            SelfMod[Self-Modification]
        end
    end

    subgraph "Agent Runtime"
        BaseAgent[Base Agent Loop<br/>Perceive→Retrieve→Reason→Execute→Verify→Learn]
        Memory[Memory Substrate<br/>Episodic|Semantic|Procedural]
        Policy[Policy Engine OPA/Rego]
    end

    subgraph "Microsoft Azure AI Stack"
        AIFoundry[Azure AI Foundry<br/>1,400+ Connectors]
        OpenAI[Azure OpenAI]
        NIM[NVIDIA NIM<br/>2.6x faster]
        EntraID[Entra Agent IDs]
    end

    subgraph "Observability - Microsoft Agent Framework"
        OTel[OpenTelemetry Tracing]
        AzMon[Azure Monitor]
        Aspire[Aspire Dashboard]
    end

    subgraph "Data Layer"
        Postgres[(PostgreSQL<br/>pgvector)]
        ANF[Azure NetApp Files<br/>67% cost reduction]
        Fabric[Azure Fabric<br/>Medallion Architecture]
        Databricks[Databricks<br/>ML Pipelines]
    end

    UI --> SSE
    Teams --> SSE
    API --> SSE
    SSE --> Council
    SSE --> Swarm
    SSE --> Stem
    SSE --> Meta

    Council --> BaseAgent
    Swarm --> BaseAgent
    Stem --> BaseAgent
    Meta --> BaseAgent

    BaseAgent --> Memory
    BaseAgent --> Policy
    BaseAgent --> AIFoundry

    AIFoundry --> OpenAI
    AIFoundry --> NIM
    AIFoundry --> EntraID

    BaseAgent --> OTel
    OTel --> AzMon
    OTel --> Aspire

    Memory --> Postgres
    BaseAgent --> ANF
    BaseAgent --> Fabric
    BaseAgent --> Databricks

    WS --> DevUI
    DevUI -.-> BaseAgent

    style ANTS Core - Biological Intelligence Patterns fill:#6366f1,stroke:#4f46e5,color:#fff
    style Microsoft Azure AI Stack fill:#0078d4,stroke:#106ebe,color:#fff
    style Observability - Microsoft Agent Framework fill:#10b981,stroke:#059669,color:#fff
```

## 2. Agent Execution Flow (6-Phase Loop)

```mermaid
sequenceDiagram
    participant User
    participant AG-UI
    participant Agent
    participant Memory
    participant LLM
    participant Policy
    participant Tools
    participant DevUI

    User->>AG-UI: Submit Request
    AG-UI->>Agent: Start Execution
    activate Agent

    Note over Agent,DevUI: Phase 1: Perceive
    Agent->>Agent: Parse & Understand Input
    Agent->>DevUI: Stream Phase 1 Data
    AG-UI-->>User: thinking: "Analyzing request..."

    Note over Agent,DevUI: Phase 2: Retrieve
    Agent->>Memory: Query Similar Experiences
    Memory-->>Agent: Relevant Context
    Agent->>DevUI: Stream Phase 2 Data
    AG-UI-->>User: thinking: "Retrieving context..."

    Note over Agent,DevUI: Phase 3: Reason
    Agent->>LLM: Generate Action Plan
    LLM-->>Agent: Reasoning + Actions
    Agent->>DevUI: Stream Phase 3 Data
    AG-UI-->>User: thinking: "Planning approach..."

    Note over Agent,DevUI: Phase 4: Execute
    Agent->>Policy: Check Action Approval
    Policy-->>Agent: Allow/Deny/RequireApproval

    alt High Risk Action
        AG-UI->>User: approval_request
        User->>AG-UI: Approve/Reject
        AG-UI->>Agent: User Decision
    end

    Agent->>Tools: Execute Action
    Tools-->>Agent: Result
    Agent->>DevUI: Stream Phase 4 Data
    AG-UI-->>User: tool_use + tool_result

    Note over Agent,DevUI: Phase 5: Verify
    Agent->>Agent: Validate Result
    Agent->>DevUI: Stream Phase 5 Data

    Note over Agent,DevUI: Phase 6: Learn
    Agent->>Memory: Store Experience
    Memory-->>Agent: Stored
    Agent->>DevUI: Stream Phase 6 Data

    Agent->>AG-UI: Final Response
    deactivate Agent
    AG-UI-->>User: response: "Task complete"
```

## 3. Decision Council Deliberation (5-Phase)

```mermaid
stateDiagram-v2
    [*] --> Propose

    Propose --> Critique: All agents submit proposals
    state Propose {
        [*] --> FinanceAgent: Budget impact
        [*] --> SecurityAgent: Risk assessment
        [*] --> OpsAgent: Feasibility
        [*] --> ComplianceAgent: Regulatory check
    }

    Critique --> Resolve: Agents critique each proposal
    state Critique {
        [*] --> IdentifyWeaknesses
        [*] --> SuggestImprovements
        [*] --> RaiseConcerns
    }

    Resolve --> Amplify: Synthesize best elements
    state Resolve {
        [*] --> MergeProposals
        [*] --> AddressObjections
        [*] --> RefineApproach
    }

    Amplify --> Verify: Build consensus
    state Amplify {
        [*] --> StrengthAssessment
        [*] --> ConsensusBuilding
        [*] --> StakeholderAlignment
    }

    Verify --> [*]: Final validation & vote
    state Verify {
        [*] --> FinalReview
        [*] --> ConsensusScore: Must be > 0.65
        [*] --> Decision: Approve/Reject/Escalate
    }
```

## 4. Swarm Coordination via Pheromone Trails

```mermaid
graph LR
    subgraph "Event Hubs - Pheromone Network"
        EH1[Opportunity Trail]
        EH2[Danger Trail]
        EH3[Resource Trail]
        EH4[Task Completion Trail]
    end

    subgraph "Agent Swarm"
        A1[Agent 1<br/>Finance]
        A2[Agent 2<br/>Security]
        A3[Agent 3<br/>HR]
        A4[Agent 4<br/>Ops]
        A5[Agent 5<br/>Data]
        A6[(...100s more)]
    end

    A1 -->|Deposit| EH1
    A1 -.->|Read| EH2
    A2 -->|Deposit| EH2
    A2 -.->|Read| EH1
    A3 -->|Deposit| EH3
    A3 -.->|Read| EH4
    A4 -->|Deposit| EH4
    A4 -.->|Read| EH3
    A5 -.->|Read| EH1
    A6 -.->|Read| EH2

    EH1 -->|Attract| A5
    EH2 -->|Repel| A6
    EH3 -->|Guide| A1
    EH4 -->|Inform| A2

    Note1[Emergent Behavior:<br/>No central coordinator<br/>Self-organizing patterns<br/>Adaptive to change]

    style Event Hubs - Pheromone Network fill:#f59e0b,stroke:#d97706
    style Agent Swarm fill:#8b5cf6,stroke:#7c3aed
```

## 5. Polymorphic Stem Cell Agent Differentiation

```mermaid
graph TD
    StemCell[Stem Cell Agent<br/>Undifferentiated<br/>Full Potential]

    StemCell -->|Context: Invoice| Finance[Finance Agent<br/>Accounting, Reconciliation]
    StemCell -->|Context: Threat| Security[Security Agent<br/>Defender, Triage]
    StemCell -->|Context: Employee| HR[HR Agent<br/>Recruiting, Benefits]
    StemCell -->|Context: Infrastructure| Ops[Ops Agent<br/>Provisioning, Monitoring]
    StemCell -->|Context: Data Quality| Data[Data Agent<br/>ETL, Validation]

    Finance --> |Specialize| FA1[Invoice Processing]
    Finance --> |Specialize| FA2[Budget Analysis]
    Finance --> |Specialize| FA3[Tax Compliance]

    Security --> |Specialize| SA1[Threat Detection]
    Security --> |Specialize| SA2[Incident Response]
    Security --> |Specialize| SA3[Compliance Audit]

    style StemCell fill:#ec4899,stroke:#db2777,color:#fff
    style Finance fill:#6366f1,stroke:#4f46e5,color:#fff
    style Security fill:#ef4444,stroke:#dc2626,color:#fff
    style HR fill:#10b981,stroke:#059669,color:#fff
    style Ops fill:#f59e0b,stroke:#d97706,color:#fff
    style Data fill:#3b82f6,stroke:#2563eb,color:#fff
```

## 6. Meta-Agent: Self-Coding Integration Builder

```mermaid
sequenceDiagram
    participant MetaAgent
    participant APIDiscovery
    participant CodeGen
    participant Testing
    participant Deployment

    MetaAgent->>APIDiscovery: Encounter New API<br/>(e.g., Stripe payment gateway)

    APIDiscovery->>APIDiscovery: Parse OpenAPI Spec
    APIDiscovery->>APIDiscovery: Analyze Endpoints
    APIDiscovery->>CodeGen: API Schema

    CodeGen->>CodeGen: Generate Python Client
    CodeGen->>CodeGen: Generate Auth Module
    CodeGen->>CodeGen: Generate Error Handling
    CodeGen->>CodeGen: Generate Tests

    CodeGen->>Testing: Run Generated Tests
    Testing->>Testing: Validate API Calls
    Testing->>Testing: Check Error Handling
    Testing-->>CodeGen: Test Results

    alt Tests Pass
        CodeGen->>Deployment: Deploy Integration
        Deployment->>MetaAgent: Integration Ready
        Note over MetaAgent: 30-60 seconds from<br/>discovery to deployment
    else Tests Fail
        CodeGen->>CodeGen: Analyze Failures
        CodeGen->>CodeGen: Regenerate Code
        CodeGen->>Testing: Retry Tests
    end
```

## 7. Memory Substrate - Three-Tier Architecture

```mermaid
graph TB
    subgraph "Input Events"
        Action[Agent Actions]
        Perception[Perceptions]
        Outcome[Outcomes]
    end

    subgraph "Memory Substrate"
        subgraph "Episodic Memory"
            Episodes[(Time-Stamped<br/>Experiences<br/>pgvector)]
            Context[Full Context<br/>Input+Output]
        end

        subgraph "Semantic Memory"
            Facts[(General Knowledge<br/>Facts & Rules<br/>pgvector)]
            Concepts[Concepts<br/>Relationships]
        end

        subgraph "Procedural Memory"
            Skills[(Learned Skills<br/>How-To Knowledge)]
            Patterns[Successful Patterns]
        end
    end

    subgraph "Retrieval"
        VectorSearch[Vector Similarity Search]
        Rerank[Contextual Reranking]
        Results[Top-K Memories]
    end

    Action --> Episodes
    Perception --> Episodes
    Outcome --> Episodes

    Episodes -.->|Generalize| Facts
    Facts -.->|Abstract| Concepts
    Episodes -.->|Extract| Skills
    Skills -.->|Refine| Patterns

    Episodes --> VectorSearch
    Facts --> VectorSearch
    Skills --> VectorSearch

    VectorSearch --> Rerank
    Rerank --> Results

    style Episodic Memory fill:#6366f1,stroke:#4f46e5,color:#fff
    style Semantic Memory fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style Procedural Memory fill:#ec4899,stroke:#db2777,color:#fff
```

## 8. SelfOps - Platform Managing Itself

```mermaid
graph LR
    subgraph "Platform Operations"
        Platform[ANTS Platform]
    end

    subgraph "SelfOps Agents"
        InfraOps[InfraOps Agent<br/>Provision Resources<br/>Scale Infrastructure]
        DataOps[DataOps Agent<br/>Monitor Data Quality<br/>Optimize Pipelines]
        AgentOps[AgentOps Agent<br/>Tune Performance<br/>A/B Testing]
        SecOps[SecOps Agent<br/>Security Monitoring<br/>Compliance Checks]
    end

    subgraph "Monitoring"
        Metrics[Metrics Collection]
        Logs[Log Analysis]
        Traces[Distributed Tracing]
    end

    Platform -->|Telemetry| Metrics
    Platform -->|Logs| Logs
    Platform -->|Traces| Traces

    Metrics --> InfraOps
    Metrics --> DataOps
    Metrics --> AgentOps
    Metrics --> SecOps

    InfraOps -->|Auto-scale| Platform
    DataOps -->|Fix Data Issues| Platform
    AgentOps -->|Optimize Agents| Platform
    SecOps -->|Apply Patches| Platform

    style SelfOps Agents fill:#10b981,stroke:#059669,color:#fff
```

## 9. Technology Stack - Three Layers

```mermaid
graph TB
    subgraph "Layer 3: ANTS Unique Features"
        Councils[Decision Councils]
        Swarms[Swarm Intelligence]
        StemCells[Polymorphic Agents]
        MetaAgents[Meta-Agents]
        SelfOps[SelfOps Teams]
    end

    subgraph "Layer 2: Microsoft Frameworks"
        AIFoundry[Azure AI Foundry<br/>1,400+ Connectors]
        SemanticKernel[Semantic Kernel<br/>Orchestration]
        AgentFramework[Agent Framework<br/>DevUI + AG-UI]
        OpenTelemetry[OpenTelemetry<br/>Observability]
        EntraID[Entra Agent IDs<br/>Security]
    end

    subgraph "Layer 1: Infrastructure (Azure + NVIDIA + NetApp)"
        AKS[Azure Kubernetes Service]
        NIM[NVIDIA NIM Microservices<br/>2.6x Faster Inference]
        ANF[Azure NetApp Files<br/>Sub-ms Latency, 67% Cost↓]
        Fabric[Azure Fabric Lakehouse]
        Databricks[Databricks ML Pipelines]
        PostgreSQL[(PostgreSQL + pgvector)]
    end

    Councils --> AIFoundry
    Swarms --> AgentFramework
    StemCells --> SemanticKernel
    MetaAgents --> AIFoundry
    SelfOps --> OpenTelemetry

    AIFoundry --> AKS
    SemanticKernel --> NIM
    AgentFramework --> AKS
    OpenTelemetry --> AKS
    EntraID --> AKS

    AKS --> ANF
    NIM --> ANF
    AKS --> Fabric
    AKS --> Databricks
    AKS --> PostgreSQL

    style Layer 3: ANTS Unique Features fill:#6366f1,stroke:#4f46e5,color:#fff
    style Layer 2: Microsoft Frameworks fill:#0078d4,stroke:#106ebe,color:#fff
    style Layer 1: Infrastructure (Azure + NVIDIA + NetApp) fill:#10b981,stroke:#059669,color:#fff
```

## 10. Data Flow - Bronze → Silver → Gold (Medallion)

```mermaid
graph LR
    subgraph "Source Systems"
        ERP[ERP System]
        CRM[CRM System]
        HR[HR System]
        IOT[IoT Sensors]
        Docs[Documents]
    end

    subgraph "Ingestion Layer"
        EventHubs[Event Hubs<br/>Real-time Streams]
        IoTHub[IoT Hub<br/>Device Data]
        Blob[Blob Storage<br/>Batch Files]
    end

    subgraph "Medallion Architecture"
        Bronze[(Bronze Layer<br/>Raw Data<br/>Azure NetApp Files)]
        Silver[(Silver Layer<br/>Cleaned Data<br/>ANF)]
        Gold[(Gold Layer<br/>Business Logic<br/>ANF)]
    end

    subgraph "Processing"
        Databricks[Databricks<br/>ETL Pipelines]
        Fabric[Azure Fabric<br/>Lakehouse]
    end

    subgraph "Serving Layer"
        Agents[ANTS Agents<br/>Business Logic]
        Analytics[PowerBI<br/>Analytics]
        API[REST API]
    end

    ERP --> EventHubs
    CRM --> EventHubs
    HR --> Blob
    IOT --> IoTHub
    Docs --> Blob

    EventHubs --> Bronze
    IoTHub --> Bronze
    Blob --> Bronze

    Bronze --> Databricks
    Databricks --> Silver
    Silver --> Fabric
    Fabric --> Gold

    Gold --> Agents
    Gold --> Analytics
    Gold --> API

    style Bronze fill:#cd7f32,stroke:#8b5a00,color:#fff
    style Silver fill:#c0c0c0,stroke:#808080,color:#000
    style Gold fill:#ffd700,stroke:#b8860b,color:#000
```

---

## Diagram Usage in Documentation

These diagrams can be embedded in:
- README.md
- Whitepaper
- GitHub Pages site
- API documentation
- Blog posts
- Technical presentations

All diagrams use Mermaid syntax and will render automatically on GitHub, GitLab, and documentation platforms supporting Mermaid.
