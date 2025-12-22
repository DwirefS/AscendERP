# ANTS Security & Cybersecurity Policies
# Governs security agent operations and threat response

package ants.security_policies

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = true

# Threat severity levels
threat_levels := {
    "critical": {
        "level": 5,
        "auto_response_allowed": true,
        "requires_human_approval": false,
        "max_response_time_seconds": 300,  # 5 minutes
        "escalation_required": true
    },
    "high": {
        "level": 4,
        "auto_response_allowed": true,
        "requires_human_approval": false,
        "max_response_time_seconds": 900,  # 15 minutes
        "escalation_required": true
    },
    "medium": {
        "level": 3,
        "auto_response_allowed": true,
        "requires_human_approval": false,
        "max_response_time_seconds": 3600,  # 1 hour
        "escalation_required": false
    },
    "low": {
        "level": 2,
        "auto_response_allowed": true,
        "requires_human_approval": false,
        "max_response_time_seconds": 14400,  # 4 hours
        "escalation_required": false
    },
    "informational": {
        "level": 1,
        "auto_response_allowed": true,
        "requires_human_approval": false,
        "max_response_time_seconds": 86400,  # 24 hours
        "escalation_required": false
    }
}

# Security agent capabilities by type
agent_capabilities := {
    "cybersecurity.defender_triage": {
        "can_isolate_device": true,
        "can_block_ip": true,
        "can_quarantine_file": true,
        "can_disable_account": false,
        "max_devices_per_action": 10,
        "requires_approval_threshold": "high"
    },
    "cybersecurity.incident_response": {
        "can_isolate_device": true,
        "can_block_ip": true,
        "can_quarantine_file": true,
        "can_disable_account": true,
        "max_devices_per_action": 100,
        "requires_approval_threshold": "critical"
    },
    "cybersecurity.threat_hunting": {
        "can_isolate_device": false,
        "can_block_ip": false,
        "can_quarantine_file": false,
        "can_disable_account": false,
        "max_devices_per_action": 0,
        "requires_approval_threshold": "none"
    },
    "selfops.secops": {
        "can_isolate_device": true,
        "can_block_ip": true,
        "can_quarantine_file": true,
        "can_disable_account": true,
        "max_devices_per_action": 1000,
        "requires_approval_threshold": "critical"
    }
}

# Prohibited actions (always require human)
prohibited_auto_actions := {
    "disable_admin_account",
    "delete_backup",
    "modify_firewall_rule_production",
    "revoke_mfa",
    "disable_logging",
    "shutdown_production_service"
}

# Critical infrastructure that requires elevated approval
critical_infrastructure := {
    "production_database",
    "authentication_service",
    "payment_gateway",
    "customer_facing_api",
    "backup_system",
    "monitoring_system"
}

# Main security action decision
decision = "ALLOW" if {
    agent_has_capability
    not is_prohibited_action
    not targets_critical_infrastructure
    within_device_limit
    threat_level_permits_auto_response
}

decision = "REQUIRE_APPROVAL" if {
    agent_has_capability
    targets_critical_infrastructure
    not is_prohibited_action
}

decision = "REQUIRE_APPROVAL" if {
    agent_has_capability
    exceeds_device_limit
    not is_prohibited_action
}

decision = "REQUIRE_APPROVAL" if {
    threat_requires_approval
    not is_prohibited_action
}

decision = "DENY" if {
    is_prohibited_action
}

decision = "DENY" if {
    not agent_has_capability
}

decision = "ESCALATE_URGENT" if {
    is_critical_threat
    targets_critical_infrastructure
    agent_has_capability
}

# Check if agent has capability for requested action
agent_has_capability if {
    agent_type := input.agent_type
    action := input.action
    capabilities := agent_capabilities[agent_type]

    # Map actions to capability flags
    capability_map := {
        "isolate_device": capabilities.can_isolate_device,
        "block_ip": capabilities.can_block_ip,
        "quarantine_file": capabilities.can_quarantine_file,
        "disable_account": capabilities.can_disable_account
    }

    capability_map[action] == true
}

# Check if action is prohibited
is_prohibited_action if {
    input.action in prohibited_auto_actions
}

# Check if action targets critical infrastructure
targets_critical_infrastructure if {
    some target in input.targets
    target in critical_infrastructure
}

# Check device count limit
within_device_limit if {
    agent_type := input.agent_type
    capabilities := agent_capabilities[agent_type]
    device_count := count(input.targets)
    device_count <= capabilities.max_devices_per_action
}

exceeds_device_limit if {
    not within_device_limit
}

# Check if threat level permits auto response
threat_level_permits_auto_response if {
    threat_severity := input.threat_severity
    threat_config := threat_levels[threat_severity]
    threat_config.auto_response_allowed == true
}

# Check if threat requires approval
threat_requires_approval if {
    agent_type := input.agent_type
    capabilities := agent_capabilities[agent_type]
    threshold := capabilities.requires_approval_threshold

    threshold != "none"

    threat_severity := input.threat_severity
    threat_level := threat_levels[threat_severity].level
    threshold_level := threat_levels[threshold].level

    threat_level >= threshold_level
}

# Check if threat is critical
is_critical_threat if {
    input.threat_severity == "critical"
}

# Check response time compliance
response_time_compliant if {
    threat_severity := input.threat_severity
    threat_config := threat_levels[threat_severity]
    max_time := threat_config.max_response_time_seconds

    elapsed_time := input.elapsed_time_seconds
    elapsed_time <= max_time
}

# Check if escalation is required
escalation_required if {
    threat_severity := input.threat_severity
    threat_config := threat_levels[threat_severity]
    threat_config.escalation_required == true
}

# Determine escalation level
escalation_level = "soc_manager" if {
    input.threat_severity == "medium"
    escalation_required
}

escalation_level = "ciso" if {
    input.threat_severity == "high"
    escalation_required
}

escalation_level = "ciso_and_ceo" if {
    input.threat_severity == "critical"
    escalation_required
}

# Data exfiltration detection
is_potential_data_exfiltration if {
    input.action == "outbound_transfer"
    input.data_size_mb > 1000
    input.destination_untrusted == true
}

is_potential_data_exfiltration if {
    input.action == "outbound_transfer"
    input.unusual_time == true
    input.data_size_mb > 100
}

# Lateral movement detection
is_potential_lateral_movement if {
    input.action == "credential_access"
    input.source_compromised_indicator > 0.7
}

is_potential_lateral_movement if {
    input.action == "remote_execution"
    input.source_device != input.target_device
    not input.authorized_admin_session
}

# Reason for decision
reason = "Agent has capability and threat permits auto-response" if {
    agent_has_capability
    threat_level_permits_auto_response
    decision == "ALLOW"
}

reason = "Action targets critical infrastructure" if {
    targets_critical_infrastructure
    decision == "REQUIRE_APPROVAL"
}

reason = sprintf("Exceeds device limit (%d devices)", [count(input.targets)]) if {
    exceeds_device_limit
    decision == "REQUIRE_APPROVAL"
}

reason = sprintf("Threat level requires %s approval", [escalation_level]) if {
    threat_requires_approval
    decision == "REQUIRE_APPROVAL"
}

reason = "Action prohibited for automation" if {
    is_prohibited_action
}

reason = "Agent lacks capability for requested action" if {
    not agent_has_capability
}

reason = "Critical threat targeting critical infrastructure - urgent escalation" if {
    decision == "ESCALATE_URGENT"
}

# Conditions for approval
conditions = [escalation_level, "incident_ticket_created"] if {
    threat_requires_approval
}

conditions = ["two_person_rule", "video_audit"] if {
    targets_critical_infrastructure
    input.threat_severity == "critical"
}

conditions = ["backup_verified", "rollback_plan"] if {
    targets_critical_infrastructure
}

# Additional monitoring required
monitoring_required = ["enhanced_logging", "real_time_alerts", "siem_correlation"] if {
    input.threat_severity in {"high", "critical"}
}

monitoring_required = ["standard_logging"] if {
    input.threat_severity in {"low", "medium", "informational"}
}

# Automated response playbook selection
response_playbook = "ransomware_containment" if {
    input.threat_type == "ransomware"
    input.threat_severity in {"high", "critical"}
}

response_playbook = "phishing_remediation" if {
    input.threat_type == "phishing"
}

response_playbook = "malware_quarantine" if {
    input.threat_type == "malware"
}

response_playbook = "credential_compromise" if {
    input.threat_type == "credential_theft"
}

response_playbook = "data_exfiltration_block" if {
    is_potential_data_exfiltration
}

# Rate limiting for security actions
action_rate_limit := {
    "hourly": {
        "isolate_device": 50,
        "block_ip": 100,
        "quarantine_file": 200,
        "disable_account": 10
    },
    "daily": {
        "isolate_device": 500,
        "block_ip": 1000,
        "quarantine_file": 2000,
        "disable_account": 100
    }
}

exceeds_rate_limit if {
    action := input.action
    period := input.time_period
    period_config := action_rate_limit[period]
    limit := period_config[action]

    input.period_action_count > limit
}

# Audit requirements
required_audit_fields = [
    "threat_id",
    "threat_severity",
    "response_playbook",
    "affected_devices",
    "action_timestamp",
    "agent_id",
    "approver_id"
] if {
    decision in {"ALLOW", "REQUIRE_APPROVAL"}
}

required_audit_fields = [
    "threat_id",
    "threat_severity",
    "escalation_level",
    "escalation_timestamp",
    "incident_commander",
    "war_room_url"
] if {
    decision == "ESCALATE_URGENT"
}
