# ANTS Financial Controls Policy
# Enforces financial transaction limits and approval workflows

package ants.financial_controls

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = true

# Transaction approval thresholds by agent type (USD)
approval_thresholds := {
    "finance.reconciliation": {
        "auto_approve_max": 10000,
        "manager_approval_max": 100000,
        "director_approval_max": 1000000,
        "cfo_approval_required": 1000000
    },
    "finance.ap_automation": {
        "auto_approve_max": 5000,
        "manager_approval_max": 50000,
        "director_approval_max": 500000,
        "cfo_approval_required": 500000
    },
    "retail.inventory": {
        "auto_approve_max": 25000,
        "manager_approval_max": 100000,
        "director_approval_max": 500000
    }
}

# Prohibited transaction types (always require human)
prohibited_auto_transactions := {
    "wire_transfer_international",
    "cryptocurrency",
    "high_risk_vendor",
    "related_party_transaction"
}

# Segregation of Duties (SoD) violations
sod_violations := {
    "create_vendor_and_pay": ["create_vendor", "create_payment"],
    "create_invoice_and_approve": ["create_invoice", "approve_invoice"],
    "journal_entry_and_post": ["create_journal_entry", "post_journal_entry"]
}

# Velocity limits (per time period)
velocity_limits := {
    "daily": {
        "transaction_count": 1000,
        "total_amount": 1000000
    },
    "hourly": {
        "transaction_count": 100,
        "total_amount": 100000
    }
}

# Main financial control decision
decision = "ALLOW" if {
    amount_within_auto_approve_threshold
    not is_prohibited_transaction
    not violates_sod
    not exceeds_velocity_limit
    passes_fraud_checks
}

decision = "REQUIRE_APPROVAL" if {
    amount_requires_approval
    not is_prohibited_transaction
}

decision = "REQUIRE_APPROVAL" if {
    is_suspicious_transaction
}

decision = "DENY" if {
    is_prohibited_transaction
}

decision = "DENY" if {
    violates_sod
}

decision = "QUARANTINE_AGENT" if {
    exceeds_velocity_limit
    is_potential_fraud
}

# Check if amount is within auto-approval threshold
amount_within_auto_approve_threshold if {
    agent_type := input.agent_type
    amount := input.amount
    threshold := approval_thresholds[agent_type].auto_approve_max
    amount <= threshold
}

# Check if amount requires approval
amount_requires_approval if {
    agent_type := input.agent_type
    amount := input.amount
    auto_threshold := approval_thresholds[agent_type].auto_approve_max
    amount > auto_threshold
}

# Determine required approval level
approval_level = "manager" if {
    agent_type := input.agent_type
    amount := input.amount
    auto_threshold := approval_thresholds[agent_type].auto_approve_max
    manager_threshold := approval_thresholds[agent_type].manager_approval_max
    amount > auto_threshold
    amount <= manager_threshold
}

approval_level = "director" if {
    agent_type := input.agent_type
    amount := input.amount
    manager_threshold := approval_thresholds[agent_type].manager_approval_max
    director_threshold := approval_thresholds[agent_type].director_approval_max
    amount > manager_threshold
    amount <= director_threshold
}

approval_level = "cfo" if {
    agent_type := input.agent_type
    amount := input.amount
    director_threshold := approval_thresholds[agent_type].director_approval_max
    amount > director_threshold
}

# Check for prohibited transactions
is_prohibited_transaction if {
    input.transaction_type in prohibited_auto_transactions
}

# Check for Segregation of Duties violations
violates_sod if {
    some violation_name, actions in sod_violations
    all_actions_by_same_agent(actions)
}

all_actions_by_same_agent(required_actions) if {
    agent_id := input.agent_id
    session_actions := input.session_actions
    some action in required_actions
    action in session_actions
    count([a | a := session_actions[_]; a in required_actions]) >= 2
}

# Check velocity limits
exceeds_velocity_limit if {
    period := input.time_period
    period_config := velocity_limits[period]

    input.period_transaction_count > period_config.transaction_count
}

exceeds_velocity_limit if {
    period := input.time_period
    period_config := velocity_limits[period]

    input.period_total_amount > period_config.total_amount
}

# Fraud detection checks
is_suspicious_transaction if {
    # Unusual time (outside business hours)
    input.transaction_hour < 6
}

is_suspicious_transaction if {
    input.transaction_hour > 22
}

is_suspicious_transaction if {
    # Amount is round number over threshold
    input.amount >= 10000
    input.amount mod 10000 == 0
}

is_suspicious_transaction if {
    # New vendor with large first transaction
    input.vendor_transaction_count == 0
    input.amount > 50000
}

is_suspicious_transaction if {
    # Duplicate transaction detection
    input.duplicate_transaction_detected == true
}

passes_fraud_checks if {
    not is_suspicious_transaction
}

is_potential_fraud if {
    exceeds_velocity_limit
    is_suspicious_transaction
}

# Geographic restrictions
requires_geographic_approval if {
    # Cross-border payments require additional scrutiny
    input.source_country != input.destination_country
    input.amount > 10000
}

# Reason for decision
reason = "Amount within auto-approval threshold" if {
    amount_within_auto_approve_threshold
    decision == "ALLOW"
}

reason = sprintf("Amount requires %s approval", [approval_level]) if {
    amount_requires_approval
    decision == "REQUIRE_APPROVAL"
}

reason = "Transaction type prohibited for automation" if {
    is_prohibited_transaction
}

reason = "Segregation of Duties violation detected" if {
    violates_sod
}

reason = "Velocity limit exceeded - potential fraud" if {
    exceeds_velocity_limit
}

reason = "Suspicious transaction pattern detected" if {
    is_suspicious_transaction
    decision == "REQUIRE_APPROVAL"
}

# Conditions for approval
conditions = [approval_level] if {
    amount_requires_approval
}

conditions = ["manager_approval", "fraud_review"] if {
    is_suspicious_transaction
}

conditions = ["two_person_rule", "video_verification"] if {
    approval_level == "cfo"
}

# Additional audit fields required
required_audit_fields = [
    "approver_id",
    "approval_timestamp",
    "ip_address",
    "device_id"
] if {
    decision == "REQUIRE_APPROVAL"
}

required_audit_fields = [
    "transaction_hash",
    "supporting_documents",
    "business_justification"
] if {
    input.amount > 100000
}
