# ANTS Authorization Policy
# Governs agent access to tools and data

package ants.authz

import future.keywords.if
import future.keywords.in

# Default deny
default decision = "DENY"

# Default audit required
default audit_required = true

# Agent tool permissions by type
agent_tool_permissions := {
    "finance.reconciliation": [
        "query_erp",
        "query_bank_statements",
        "match_transactions",
        "flag_discrepancy",
        "generate_report"
    ],
    "retail.inventory": [
        "query_inventory",
        "update_stock_levels",
        "create_purchase_order",
        "generate_reorder_report"
    ],
    "cybersecurity.defender": [
        "query_defender_api",
        "enrich_with_threat_intel",
        "query_asset_inventory",
        "check_user_context",
        "create_incident",
        "run_investigation"
    ],
    "selfops.infra": [
        "terraform_plan",
        "terraform_apply",
        "helm_upgrade",
        "kubectl_scale",
        "monitor_metrics"
    ]
}

# High-risk tools requiring approval
high_risk_tools := {
    "isolate_endpoint",
    "delete_data",
    "modify_production",
    "terraform_apply"
}

# Data classification access levels
data_access_levels := {
    "public": 1,
    "internal": 2,
    "confidential": 3,
    "restricted": 4,
    "top_secret": 5
}

# Agent clearance levels
agent_clearance := {
    "finance.reconciliation": 3,
    "retail.inventory": 2,
    "cybersecurity.defender": 4,
    "selfops.infra": 3
}

# Main authorization decision
decision = "ALLOW" if {
    is_tool_allowed
    not is_high_risk_action
}

decision = "REQUIRE_APPROVAL" if {
    is_tool_allowed
    is_high_risk_action
}

decision = "ALLOW_WITH_REDACTION" if {
    is_tool_allowed
    requires_data_redaction
}

# Check if tool is allowed for agent type
is_tool_allowed if {
    agent_type := input.agent_id
    tool := input.tool
    allowed_tools := agent_tool_permissions[agent_type]
    tool in allowed_tools
}

# Check if action is high-risk
is_high_risk_action if {
    input.tool in high_risk_tools
}

is_high_risk_action if {
    input.estimated_impact == "high"
}

is_high_risk_action if {
    input.args.amount > 100000
}

# Check if data access requires redaction
requires_data_redaction if {
    input.action == "data_access"
    data_level := data_access_levels[input.classification]
    agent_level := agent_clearance[input.agent_id]
    data_level > agent_level
}

# Reason for decision
reason = "Tool not authorized for agent type" if {
    not is_tool_allowed
}

reason = "High-risk action requires human approval" if {
    is_tool_allowed
    is_high_risk_action
}

reason = "Data classification exceeds agent clearance" if {
    is_tool_allowed
    requires_data_redaction
}

# Conditions for approval
conditions = ["manager_approval", "audit_log"] if {
    is_high_risk_action
}

# Fields to redact
redactions = ["ssn", "credit_card", "password"] if {
    requires_data_redaction
}
