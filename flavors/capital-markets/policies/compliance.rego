# Capital Markets Compliance Policy
# Enforces KYC/AML, sanctions screening, reporting obligations,
# insider trading restrictions, and best execution requirements

package capital_markets.compliance

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = true
default reason = "Compliance requirements not met"

# Regulatory frameworks
regulatory_frameworks := {
    "us": ["SEC", "FINRA", "CFTC", "DODD_FRANK", "BANK_SECRECY_ACT"],
    "eu": ["MiFID_II", "GDPR", "EMIR", "MAD_MAR"],
    "uk": ["FCA", "PRA", "SDRT"],
    "global": ["AML", "KYC", "OFAC_SANCTIONS", "EU_SANCTIONS", "UN_SANCTIONS"]
}

# Client classifications
client_types := {
    "retail": {
        "requires_suitability": true,
        "requires_risk_warning": true,
        "max_leverage": 2.0,
        "requires_kyc_doc": 2,  # 2 forms of ID
        "requires_address_verification": true
    },
    "professional": {
        "requires_suitability": false,
        "requires_risk_warning": false,
        "max_leverage": 5.0,
        "requires_kyc_doc": 1,
        "requires_address_verification": false
    },
    "institutional": {
        "requires_suitability": false,
        "requires_risk_warning": false,
        "max_leverage": 10.0,
        "requires_kyc_doc": 0,
        "requires_address_verification": false
    }
}

# KYC status codes
kyc_statuses := {
    "approved": "KYC approved and current",
    "pending": "KYC pending review",
    "expired": "KYC documentation expired",
    "rejected": "KYC rejected",
    "suspended": "Account suspended"
}

# Sanctions lists
sanctions_lists := [
    "OFAC_SDN",
    "OFAC_CONSOLIDATED",
    "EU_CONSOLIDATED_SANCTIONS",
    "UN_SECURITY_COUNCIL",
    "HM_TREASURY_SANCTIONS"
]

# Trade reporting thresholds
reporting_thresholds := {
    "large_trade_reporting": 50_000_000,  # $50M
    "suspicious_activity_threshold": 10_000,  # $10K
    "currency_transaction_threshold": 10_000,  # $10K
    "beneficial_ownership_threshold": 25  # 25% stake
}

# Blackout period definitions
blackout_periods := {
    "quarterly_earnings": 30,  # days before/after earnings
    "material_events": 14,  # days around material announcements
    "executive_blackout": true  # C-suite restricted during blackouts
}

# Main compliance decision logic
decision = "ALLOW" if {
    client_kyc_approved
    not client_on_sanctions_list
    not trading_in_blackout_period
    suitability_met
    has_best_execution_doc
}

decision = "REQUIRE_APPROVAL" if {
    client_kyc_approved
    not client_on_sanctions_list
    requires_kyc_renewal_soon
}

decision = "REQUIRE_APPROVAL" if {
    large_trade_requires_reporting
}

decision = "REQUIRE_APPROVAL" if {
    requires_suspicious_activity_report
}

decision = "DENY" if {
    not client_kyc_approved
    client_kyc_status == "rejected"
}

decision = "DENY" if {
    client_on_sanctions_list
}

decision = "DENY" if {
    trading_in_blackout_period
    not is_authorized_exception
}

decision = "QUARANTINE_AND_REPORT" if {
    client_on_sanctions_list
}

decision = "ESCALATE" if {
    requires_suspicious_activity_report
}

# KYC/AML Checks
client_kyc_approved if {
    kyc_status := input.client_kyc_status
    kyc_status == "approved"
    not input.kyc_expired
}

requires_kyc_renewal_soon if {
    days_until_expiry := input.kyc_days_to_expiry
    days_until_expiry < 30
    days_until_expiry > 0
}

requires_kyc_update if {
    days_since_kyc := input.days_since_last_kyc
    days_since_kyc > 365
}

# Sanctions and blacklist screening
client_on_sanctions_list if {
    some list in sanctions_lists
    client_name := input.client_name
    sanctioned_entities[list][_] == client_name
}

client_on_sanctions_list if {
    some list in sanctions_lists
    client_id := input.client_id
    sanctioned_ids[list][_] == client_id
}

# Country-based risk screening
high_risk_jurisdictions := {
    "iran", "north_korea", "syria", "crimea", "myanmar"
}

jurisdiction_high_risk if {
    jurisdiction := input.client_jurisdiction
    jurisdiction in high_risk_jurisdictions
}

# Suitability requirements
suitability_met if {
    client_type := input.client_type
    client_categories := client_types[client_type]

    # Retail clients must have suitability assessment
    client_categories.requires_suitability == true
    input.has_suitability_doc == true
    input.suitability_approved == true
}

suitability_met if {
    client_type := input.client_type
    client_categories := client_types[client_type]

    # Professional/Institutional clients don't require suitability
    client_categories.requires_suitability == false
}

# Leverage appropriateness
leverage_appropriate if {
    client_type := input.client_type
    client_categories := client_types[client_type]
    max_leverage := client_categories.max_leverage

    input.requested_leverage <= max_leverage
}

# Best execution requirements
has_best_execution_doc if {
    input.trade_amount < reporting_thresholds.large_trade_reporting
}

has_best_execution_doc if {
    input.trade_amount >= reporting_thresholds.large_trade_reporting
    input.has_execution_report == true
    input.venue_selection_documented == true
}

requires_best_execution_doc if {
    input.trade_amount > reporting_thresholds.large_trade_reporting
}

# Insider trading restrictions
trading_in_blackout_period if {
    blackout_active := input.blackout_period_active
    blackout_active == true
    input.trader_level in {"executive", "research", "tm"}
}

is_authorized_exception if {
    input.has_blackout_exception == true
    input.exception_approved_by == "compliance"
}

# Reportable transactions
large_trade_requires_reporting if {
    input.trade_amount >= reporting_thresholds.large_trade_reporting
}

requires_suspicious_activity_report if {
    # Unusual transaction patterns
    input.amount_pct_of_daily_volume > 0.50
    input.trade_amount > reporting_thresholds.suspicious_activity_threshold
}

requires_suspicious_activity_report if {
    # Rapid sequence of transactions
    input.hourly_transaction_count > 10
}

requires_suspicious_activity_report if {
    # Structuring to avoid reporting (splitting $10K+ into smaller chunks)
    input.potential_structuring_detected == true
}

requires_suspicious_activity_report if {
    # High-risk jurisdiction + large amount
    jurisdiction_high_risk
    input.trade_amount > 100_000
}

requires_suspicious_activity_report if {
    # Unusual time or pattern
    input.unusual_timing == true
    input.trade_amount > 50_000
}

# Document verification
has_required_documents if {
    client_type := input.client_type
    client_info := client_types[client_type]
    required_docs := client_info.requires_kyc_doc

    submitted_docs := count(input.kyc_documents)
    submitted_docs >= required_docs
}

address_verified if {
    client_type := input.client_type
    client_info := client_types[client_type]

    not client_info.requires_address_verification
}

address_verified if {
    client_type := input.client_type
    client_info := client_types[client_type]

    client_info.requires_address_verification == true
    input.address_verified == true
}

# Beneficial ownership disclosure
requires_beneficial_ownership if {
    input.ownership_stake > reporting_thresholds.beneficial_ownership_threshold
}

beneficial_ownership_disclosed if {
    not requires_beneficial_ownership
}

beneficial_ownership_disclosed if {
    requires_beneficial_ownership
    input.beneficial_owner_disclosed == true
}

# Reporting obligations
required_reports = reports if {
    large_trade_requires_reporting
    reports := ["LARGE_TRADE_REPORT"]
}

required_reports = reports if {
    requires_suspicious_activity_report
    reports := ["SUSPICIOUS_ACTIVITY_REPORT", "ESCALATION"]
}

required_reports = reports if {
    jurisdiction_high_risk
    reports := ["JURISDICTION_RISK_REPORT"]
}

# Approval chains
approval_level = "NONE" if {
    decision == "ALLOW"
}

approval_level = "COMPLIANCE_OFFICER" if {
    decision == "REQUIRE_APPROVAL"
    large_trade_requires_reporting
}

approval_level = "COMPLIANCE_MANAGER" if {
    requires_suspicious_activity_report
}

approval_level = "EXECUTIVE_ESCALATION" if {
    client_on_sanctions_list
}

# Detailed reasoning
reason = "KYC approved, sanctions clear, best execution documented" if {
    decision == "ALLOW"
}

reason = sprintf("KYC expiring in %d days, renewal required",
    [input.kyc_days_to_expiry]) if {
    decision == "REQUIRE_APPROVAL"
    requires_kyc_renewal_soon
}

reason = "Large trade exceeding $50M requires reporting documentation" if {
    large_trade_requires_reporting
}

reason = "Suspicious activity pattern detected - SAR required" if {
    requires_suspicious_activity_report
}

reason = "Client KYC status rejected or expired" if {
    not client_kyc_approved
}

reason = sprintf("Client on sanctions list: %s", [input.client_name]) if {
    client_on_sanctions_list
}

reason = "Trading during blackout period restricted for this trader level" if {
    trading_in_blackout_period
    not is_authorized_exception
}

reason = sprintf("Suitability assessment required for %s client", [input.client_type]) if {
    not suitability_met
}

# Conditions for approval
conditions = ["kyc_renewal_pending"] if {
    requires_kyc_renewal_soon
}

conditions = ["best_execution_documentation"] if {
    large_trade_requires_reporting
}

conditions = ["suspicious_activity_report", "compliance_escalation"] if {
    requires_suspicious_activity_report
}

conditions = ["trading_halt"] if {
    client_on_sanctions_list
}

# Required audit and reporting fields
required_audit_fields = [
    "transaction_id",
    "client_id",
    "client_name",
    "kyc_status",
    "kyc_approval_date",
    "sanctions_screening_date",
    "amount",
    "transaction_timestamp",
    "trader_id",
    "approved_by"
] if {
    decision in {"ALLOW", "REQUIRE_APPROVAL"}
}

required_audit_fields = [
    "transaction_id",
    "client_id",
    "client_name",
    "kyc_status",
    "sanctions_screening_result",
    "blackout_period_status",
    "rejection_reason",
    "amount",
    "rejection_timestamp"
] if {
    decision == "DENY"
}

required_audit_fields = [
    "incident_id",
    "client_id",
    "client_name",
    "suspicious_indicator",
    "sar_filed_timestamp",
    "sar_reference_number",
    "escalated_to",
    "regulatory_filing"
] if {
    decision == "QUARANTINE_AND_REPORT"
}

# Fictional data for demo - in production would query actual databases
sanctioned_entities := {
    "OFAC_SDN": {"ENTITY_A", "ENTITY_B"},
    "EU_SANCTIONS": {"COMPANY_X", "COMPANY_Y"}
}

sanctioned_ids := {
    "OFAC_SDN": {"ID_123", "ID_456"},
    "EU_SANCTIONS": {"ID_789"}
}
