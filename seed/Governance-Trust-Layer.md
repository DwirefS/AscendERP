# Governance & Trust Layer
**ANTS: policy, safety, auditability, supply-chain security, and enterprise controls**

This document defines the *Trust Layer* that makes ANTS enterprise-grade.

---

## 1) Core Principle
> **Autonomy without accountability is not enterprise-ready.**  
ANTS is built to be autonomous *and* governed: every action is policy-gated, attributable, and auditable.

---

## 2) Policy-as-Code (Action Gate)
### 2.1 Tool Call Envelope (required)
Every agent action is wrapped in a standard envelope:

```json
{
  "trace_id": "uuid",
  "tenant_id": "string",
  "user_id": "aad|oidc|service",
  "agent_id": "ants:finance.recon.v1",
  "policy_context": {
    "role": "CFO",
    "data_class": ["SOX","PII"],
    "environment": "prod"
  },
  "intent": "post_journal_entry",
  "tool": "erp.post_journal",
  "args": { "amount": 12000, "account": "..." },
  "model": { "name": "nim:nemotron", "version": "x.y.z" },
  "artifacts": {
    "inputs": ["anf://.../invoice.pdf"],
    "evidence": ["search://...chunk/123"]
  }
}
```

### 2.2 Policy Decision Outcomes
- `ALLOW` (auto-execute)
- `DENY` (block)
- `REQUIRE_APPROVAL` (human-in-the-loop)
- `ALLOW_WITH_REDACTION` (output constraints)
- `QUARANTINE_AGENT` (security posture response)

### 2.3 Example Policy Controls
- Finance: SOX control gates for postings above threshold
- Healthcare: PHI access restricted by clinician role
- Retail: reorder limit caps and anomaly triggers
- Manufacturing: maintenance actions require safety constraints

---

## 3) Human-in-the-Loop (HITL)
### 3.1 Approval Protocol
For `REQUIRE_APPROVAL`, the system creates:
- an approval ticket (Teams/web)
- an evidence bundle
- a diff of proposed changes
- a rollback plan

Approver choices:
- approve once
- approve for session
- approve for policy template
- deny + open incident

---

## 4) Audit Receipts (Forensics Grade)
### 4.1 Receipt Schema
Receipts are immutable records written to the memory substrate:

```json
{
  "receipt_id": "uuid",
  "trace_id": "uuid",
  "timestamp": "ISO-8601",
  "actor": { "user_id": "...", "agent_id": "..." },
  "action": { "tool": "...", "args_hash": "sha256" },
  "policy": { "decision": "ALLOW", "policy_hash": "sha256" },
  "data_lineage": { "sources": ["..."], "outputs": ["..."] },
  "model_lineage": { "model": "nim:...", "prompt_hash": "sha256" },
  "result": { "status": "success|fail", "error": "..." }
}
```

### 4.2 Storage Strategy
- hot receipts: Postgres for queryability
- immutable receipts: ANF append-only logs + snapshots
- DR: replicated volumes

---

## 5) Security Posture for Agents
### 5.1 Identity
- Each agent has a distinct identity (service principal / workload identity)
- Principle of least privilege applies to every tool and data path

### 5.2 Segmentation
- separate namespaces/node pools for:
  - inference
  - data services
  - control plane
  - SelfOps

### 5.3 Quarantine
If an agent deviates (drift, abnormal tool calls):
- revoke tokens
- block network egress
- freeze memory writes
- snapshot for investigation

---

## 6) Data Governance
### 6.1 Classification
Tag data as:
- Public / Internal / Confidential
- PII / PHI / PCI / SOX
- Retention class (7y, 10y, etc.)

### 6.2 Retrieval Filters
Retrieval must enforce:
- RBAC/ABAC filters
- document ACLs (where applicable)
- redaction policies at output time

---

## 7) Model Governance
### 7.1 Model Lifecycle
- registry of models used per environment
- canary rollout and rollback
- evaluation gates before promotion

### 7.2 Drift Detection
- prompt drift
- embedding drift
- retrieval drift
- response quality regression

---

## 8) CLEAR Metrics as Governance Inputs
CLEAR isn’t just reporting—policy can use it:
- If cost spikes → throttle / switch to smaller model
- If latency exceeds SLO → scale inference / degrade gracefully
- If efficacy drops → rollback model/index
- If assurance fails → require approvals
- If reliability drops → incident and freeze deployments

---

## 9) Supply Chain Security
### 9.1 SBOM
- generate SBOM for every build artifact
- store SBOM alongside release tags

### 9.2 Signed Builds
- sign container images
- verify signatures at deploy time

### 9.3 Dependency Hygiene
- pin versions
- automated vulnerability scanning
- “no new dependency without license + security review”

---

## 10) What Makes This Enterprise-Grade
- policy-gated autonomy
- immutable receipts
- rollback-first architecture
- strong identity segmentation
- continuous evaluation gates
- auditable and reproducible builds
