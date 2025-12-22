# ANTS Agent Lifecycle Management Policies
# Governs agent sleep/wake states, resource allocation, and cost controls

package ants.agent_lifecycle

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = false

# Agent tier configurations (cost vs performance)
agent_tiers := {
    "critical": {
        "level": 5,
        "max_sleep_duration_hours": 1,
        "min_wake_duration_minutes": 5,
        "max_concurrent_instances": 100,
        "auto_scale_enabled": true,
        "cost_per_hour": 2.50,
        "always_warm": true
    },
    "high_priority": {
        "level": 4,
        "max_sleep_duration_hours": 4,
        "min_wake_duration_minutes": 2,
        "max_concurrent_instances": 50,
        "auto_scale_enabled": true,
        "cost_per_hour": 1.50,
        "always_warm": false
    },
    "standard": {
        "level": 3,
        "max_sleep_duration_hours": 24,
        "min_wake_duration_minutes": 1,
        "max_concurrent_instances": 20,
        "auto_scale_enabled": true,
        "cost_per_hour": 0.75,
        "always_warm": false
    },
    "batch": {
        "level": 2,
        "max_sleep_duration_hours": 168,  # 1 week
        "min_wake_duration_minutes": 1,
        "max_concurrent_instances": 10,
        "auto_scale_enabled": false,
        "cost_per_hour": 0.25,
        "always_warm": false
    },
    "on_demand": {
        "level": 1,
        "max_sleep_duration_hours": 720,  # 30 days
        "min_wake_duration_minutes": 1,
        "max_concurrent_instances": 5,
        "auto_scale_enabled": false,
        "cost_per_hour": 0.10,
        "always_warm": false
    }
}

# Agent type to tier mapping
agent_tier_mapping := {
    "finance.reconciliation": "high_priority",
    "finance.ap_automation": "standard",
    "cybersecurity.defender_triage": "critical",
    "cybersecurity.incident_response": "critical",
    "cybersecurity.threat_hunting": "standard",
    "retail.inventory": "standard",
    "retail.demand_forecasting": "batch",
    "manufacturing.predictive_maintenance": "high_priority",
    "healthcare.patient_triage": "critical",
    "hr.recruitment": "standard",
    "hr.onboarding": "standard",
    "crm.lead_scoring": "standard",
    "supply_chain.route_optimization": "high_priority",
    "selfops.infraops": "high_priority",
    "selfops.dataops": "high_priority",
    "selfops.agentops": "critical",
    "selfops.secops": "critical"
}

# Resource limits per agent tier
resource_limits := {
    "critical": {
        "max_memory_gb": 32,
        "max_cpu_cores": 8,
        "max_gpu_count": 2,
        "max_storage_gb": 500,
        "network_egress_gb_per_day": 1000
    },
    "high_priority": {
        "max_memory_gb": 16,
        "max_cpu_cores": 4,
        "max_gpu_count": 1,
        "max_storage_gb": 200,
        "network_egress_gb_per_day": 500
    },
    "standard": {
        "max_memory_gb": 8,
        "max_cpu_cores": 2,
        "max_gpu_count": 0,
        "max_storage_gb": 100,
        "network_egress_gb_per_day": 200
    },
    "batch": {
        "max_memory_gb": 4,
        "max_cpu_cores": 1,
        "max_gpu_count": 0,
        "max_storage_gb": 50,
        "network_egress_gb_per_day": 100
    },
    "on_demand": {
        "max_memory_gb": 2,
        "max_cpu_cores": 1,
        "max_gpu_count": 0,
        "max_storage_gb": 20,
        "network_egress_gb_per_day": 50
    }
}

# Business hours by timezone (agent wake schedule)
business_hours := {
    "US/Eastern": {
        "start_hour": 8,
        "end_hour": 18,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    "US/Pacific": {
        "start_hour": 8,
        "end_hour": 18,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    "Europe/London": {
        "start_hour": 9,
        "end_hour": 17,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    "Asia/Singapore": {
        "start_hour": 9,
        "end_hour": 18,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    "24x7": {
        "start_hour": 0,
        "end_hour": 24,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    }
}

# Main lifecycle decision
decision = "ALLOW_WAKE" if {
    is_within_business_hours
    not exceeds_concurrent_limit
    not exceeds_cost_budget
    tier_permits_wake
}

decision = "ALLOW_WAKE" if {
    is_critical_agent
    not exceeds_cost_budget
    not exceeds_concurrent_limit
}

decision = "ALLOW_WAKE" if {
    has_urgent_task
    not exceeds_cost_budget
}

decision = "ALLOW_SLEEP" if {
    not is_within_business_hours
    not is_critical_agent
    sleep_duration_valid
}

decision = "ALLOW_SLEEP" if {
    idle_time_exceeds_threshold
    not has_pending_tasks
    sleep_duration_valid
}

decision = "FORCE_SLEEP" if {
    exceeds_cost_budget
    not is_critical_agent
}

decision = "FORCE_SLEEP" if {
    exceeds_resource_limits
}

decision = "DENY_WAKE" if {
    exceeds_concurrent_limit
    not is_critical_agent
}

decision = "DENY_WAKE" if {
    exceeds_cost_budget
}

decision = "REQUIRE_APPROVAL" if {
    exceeds_cost_budget
    is_critical_agent
}

# Check if within business hours
is_within_business_hours if {
    agent_type := input.agent_type
    timezone := input.timezone
    hours := business_hours[timezone]

    current_hour := input.current_hour
    current_day := input.current_day

    current_hour >= hours.start_hour
    current_hour < hours.end_hour
    current_day in hours.days
}

# Check if agent is critical tier
is_critical_agent if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier == "critical"
}

# Check concurrent instance limit
exceeds_concurrent_limit if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]
    max_instances := tier_config.max_concurrent_instances

    current_instances := input.current_instance_count
    current_instances >= max_instances
}

# Check cost budget
exceeds_cost_budget if {
    tenant_id := input.tenant_id
    current_spend := input.current_monthly_spend
    budget := input.monthly_budget

    current_spend >= budget
}

# Check if tier permits wake
tier_permits_wake if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]

    # Always warm agents are always permitted
    tier_config.always_warm == true
}

tier_permits_wake if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]

    # Check if sleep duration hasn't exceeded max
    sleep_duration_hours := input.sleep_duration_hours
    max_sleep := tier_config.max_sleep_duration_hours

    sleep_duration_hours <= max_sleep
}

# Check if sleep duration is valid
sleep_duration_valid if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]

    requested_sleep_hours := input.requested_sleep_hours
    max_sleep := tier_config.max_sleep_duration_hours

    requested_sleep_hours <= max_sleep
}

# Check idle time threshold
idle_time_exceeds_threshold if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]

    idle_minutes := input.idle_minutes
    min_wake_minutes := tier_config.min_wake_duration_minutes

    # Agent has been idle for 2x minimum wake duration
    idle_minutes >= (min_wake_minutes * 2)
}

# Check for pending tasks
has_pending_tasks if {
    input.pending_task_count > 0
}

# Check for urgent tasks
has_urgent_task if {
    input.task_priority >= 8
}

has_urgent_task if {
    input.task_type in {"security_incident", "system_outage", "data_breach"}
}

# Check resource limits
exceeds_resource_limits if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    limits := resource_limits[tier]

    requested_memory := input.requested_memory_gb
    requested_memory > limits.max_memory_gb
}

exceeds_resource_limits if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    limits := resource_limits[tier]

    requested_cpu := input.requested_cpu_cores
    requested_cpu > limits.max_cpu_cores
}

exceeds_resource_limits if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    limits := resource_limits[tier]

    requested_gpu := input.requested_gpu_count
    requested_gpu > limits.max_gpu_count
}

# Auto-scaling decision
auto_scale_permitted if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]

    tier_config.auto_scale_enabled == true
}

scale_up_recommended if {
    auto_scale_permitted
    input.queue_depth > 100
    not exceeds_concurrent_limit
    not exceeds_cost_budget
}

scale_down_recommended if {
    auto_scale_permitted
    input.queue_depth < 10
    input.current_instance_count > 1
}

# Agent checkpoint/snapshot requirements
requires_checkpoint if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier in {"critical", "high_priority"}
}

requires_checkpoint if {
    input.action == "sleep"
    input.memory_state_important == true
}

checkpoint_destination = "anf_ultra" if {
    is_critical_agent
}

checkpoint_destination = "anf_premium" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier == "high_priority"
}

checkpoint_destination = "anf_standard" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier in {"standard", "batch", "on_demand"}
}

# Cost optimization recommendations
cost_optimization = "consider_sleep" if {
    idle_time_exceeds_threshold
    not is_critical_agent
    input.current_monthly_spend > (input.monthly_budget * 0.8)
}

cost_optimization = "downgrade_tier" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier != "on_demand"

    input.avg_utilization_pct < 20
}

cost_optimization = "upgrade_tier" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier != "critical"

    input.avg_utilization_pct > 90
    input.task_failure_rate > 0.1
}

# Reason for decision
reason = "Within business hours and under limits" if {
    is_within_business_hours
    decision == "ALLOW_WAKE"
}

reason = "Critical agent - always permitted" if {
    is_critical_agent
    decision == "ALLOW_WAKE"
}

reason = "Urgent task requires immediate wake" if {
    has_urgent_task
    decision == "ALLOW_WAKE"
}

reason = "Outside business hours" if {
    not is_within_business_hours
    decision == "ALLOW_SLEEP"
}

reason = sprintf("Idle for %d minutes", [input.idle_minutes]) if {
    idle_time_exceeds_threshold
    decision == "ALLOW_SLEEP"
}

reason = "Cost budget exceeded - forcing sleep" if {
    exceeds_cost_budget
    decision == "FORCE_SLEEP"
}

reason = "Resource limits exceeded" if {
    exceeds_resource_limits
    decision == "FORCE_SLEEP"
}

reason = sprintf("Concurrent instance limit reached (%d/%d)", [input.current_instance_count, max_limit]) if {
    exceeds_concurrent_limit
    decision == "DENY_WAKE"
} {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier_config := agent_tiers[tier]
    max_limit := tier_config.max_concurrent_instances
}

reason = "Monthly budget exceeded - approval required" if {
    exceeds_cost_budget
    is_critical_agent
    decision == "REQUIRE_APPROVAL"
}

# Conditions for lifecycle actions
conditions = ["save_checkpoint", checkpoint_destination] if {
    requires_checkpoint
    input.action == "sleep"
}

conditions = ["restore_checkpoint", checkpoint_destination] if {
    requires_checkpoint
    input.action == "wake"
}

conditions = ["budget_override_approval"] if {
    exceeds_cost_budget
    is_critical_agent
}

# Monitoring and metrics
metrics_required = [
    "wake_time",
    "sleep_time",
    "utilization_pct",
    "cost_per_task",
    "task_completion_rate"
] if {
    decision in {"ALLOW_WAKE", "ALLOW_SLEEP"}
}

# Audit requirements (only for critical operations)
audit_required = true if {
    decision in {"FORCE_SLEEP", "REQUIRE_APPROVAL"}
}

audit_required = true if {
    is_critical_agent
}

# Sleep schedule recommendation
recommended_sleep_schedule = "nights_and_weekends" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier in {"standard", "batch", "on_demand"}
    input.timezone != "24x7"
}

recommended_sleep_schedule = "low_activity_periods" if {
    agent_type := input.agent_type
    tier := agent_tier_mapping[agent_type]
    tier == "high_priority"
    input.timezone != "24x7"
}

recommended_sleep_schedule = "none" if {
    is_critical_agent
}
