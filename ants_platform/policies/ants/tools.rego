# ANTS Tool Access Policy
# Governs which agents can use which tools

package ants.tools

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default audit_required = true

# Tool categories
tool_categories := {
    "read_only": [
        "query_erp",
        "query_bank_statements",
        "query_inventory",
        "query_defender_api",
        "enrich_with_threat_intel",
        "monitor_metrics"
    ],
    "write": [
        "create_journal_entry",
        "update_stock_levels",
        "create_purchase_order",
        "update_alert_status",
        "create_incident"
    ],
    "administrative": [
        "terraform_apply",
        "helm_upgrade",
        "kubectl_scale",
        "isolate_endpoint"
    ]
}

# Rate limits by tool category (calls per minute)
rate_limits := {
    "read_only": 100,
    "write": 20,
    "administrative": 5
}

# Tool execution time limits (seconds)
time_limits := {
    "read_only": 30,
    "write": 60,
    "administrative": 300
}

# Check tool category
get_tool_category(tool) = category if {
    some category, tools in tool_categories
    tool in tools
}

# Validate tool call
decision = "ALLOW" if {
    tool := input.tool
    category := get_tool_category(tool)
    category == "read_only"
}

decision = "ALLOW" if {
    tool := input.tool
    category := get_tool_category(tool)
    category == "write"
    input.context.session_verified == true
}

decision = "REQUIRE_APPROVAL" if {
    tool := input.tool
    category := get_tool_category(tool)
    category == "administrative"
}

# Rate limit check (would be enforced at runtime)
rate_limit := rate_limits[category] if {
    category := get_tool_category(input.tool)
}

# Time limit for tool
time_limit := time_limits[category] if {
    category := get_tool_category(input.tool)
}

reason = concat(" ", ["Tool", input.tool, "requires", get_tool_category(input.tool), "permissions"])
