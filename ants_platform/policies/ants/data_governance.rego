# ANTS Data Governance Policy
# Controls data access, retention, and privacy compliance

package ants.data_governance

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = true

# Data classification levels
data_classifications := {
    "public": {
        "level": 1,
        "retention_days": 365,
        "encryption_required": false,
        "pii_allowed": false
    },
    "internal": {
        "level": 2,
        "retention_days": 1095,  # 3 years
        "encryption_required": true,
        "pii_allowed": false
    },
    "confidential": {
        "level": 3,
        "retention_days": 2555,  # 7 years
        "encryption_required": true,
        "pii_allowed": true
    },
    "restricted": {
        "level": 4,
        "retention_days": 2555,
        "encryption_required": true,
        "pii_allowed": true,
        "mfa_required": true
    }
}

# PII field types that require special handling
pii_fields := {
    "ssn",
    "tax_id",
    "credit_card",
    "bank_account",
    "passport",
    "drivers_license",
    "email",
    "phone",
    "address",
    "biometric_data"
}

# GDPR-protected regions
gdpr_regions := {"EU", "UK", "EEA"}

# CCPA-protected regions
ccpa_regions := {"CA"}  # California

# Financial data regulations
financial_regulations := {
    "SOX": ["transaction", "journal_entry", "audit_log"],
    "PCI_DSS": ["payment", "credit_card"],
    "GLBA": ["customer_financial_data"]
}

# Main data access decision
decision = "ALLOW" if {
    has_clearance_for_classification
    not contains_pii_without_authorization
    not violates_retention_policy
    encryption_requirements_met
}

decision = "ALLOW_WITH_REDACTION" if {
    has_clearance_for_classification
    contains_pii_without_authorization
    redaction_possible
}

decision = "DENY" if {
    not has_clearance_for_classification
}

decision = "REQUIRE_APPROVAL" if {
    is_cross_border_transfer
    requires_explicit_consent
}

# Check if agent has clearance for data classification
has_clearance_for_classification if {
    agent_type := input.agent_type
    data_class := input.data_classification
    agent_level := input.agent_clearance_level
    data_level := data_classifications[data_class].level
    agent_level >= data_level
}

# Check for unauthorized PII access
contains_pii_without_authorization if {
    has_pii_fields
    not input.pii_authorized
}

has_pii_fields if {
    some field in input.requested_fields
    field in pii_fields
}

# Check if redaction is possible
redaction_possible if {
    has_pii_fields
    input.operation == "read"
}

# Check retention policy compliance
violates_retention_policy if {
    data_age_days := input.data_age_days
    classification := input.data_classification
    max_retention := data_classifications[classification].retention_days
    data_age_days > max_retention
}

# Check encryption requirements
encryption_requirements_met if {
    classification := input.data_classification
    encryption_required := data_classifications[classification].encryption_required
    encryption_required == input.is_encrypted
}

encryption_requirements_met if {
    classification := input.data_classification
    not data_classifications[classification].encryption_required
}

# Check for cross-border data transfer
is_cross_border_transfer if {
    input.source_region != input.destination_region
    is_regulated_region(input.source_region)
}

is_regulated_region(region) if {
    region in gdpr_regions
}

is_regulated_region(region) if {
    region in ccpa_regions
}

# Check if explicit consent is required
requires_explicit_consent if {
    is_cross_border_transfer
    input.data_subject_consent == false
}

requires_explicit_consent if {
    input.purpose == "marketing"
    input.data_subject_consent == false
}

# Check financial regulation compliance
requires_financial_compliance if {
    some regulation, entity_types in financial_regulations
    input.entity_type in entity_types
}

# Reason for decision
reason = "Data classification exceeds agent clearance" if {
    not has_clearance_for_classification
}

reason = "PII access requires explicit authorization" if {
    contains_pii_without_authorization
}

reason = "Data exceeds retention policy" if {
    violates_retention_policy
}

reason = "Cross-border transfer requires approval" if {
    is_cross_border_transfer
}

reason = "Encryption required for this classification" if {
    not encryption_requirements_met
}

# Fields to redact
redactions = pii_fields if {
    contains_pii_without_authorization
    redaction_possible
}

# Audit requirements
audit_required = true if {
    has_pii_fields
}

audit_required = true if {
    requires_financial_compliance
}

# Conditions for approval
conditions = ["data_protection_officer_approval", "legal_review"] if {
    is_cross_border_transfer
}

conditions = ["explicit_consent", "purpose_limitation"] if {
    requires_explicit_consent
}
