# Business Continuity and Disaster Recovery Module for ANTS
# Implements cross-region failover and backup strategies

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "primary_location" {
  type        = string
  description = "Primary Azure region"
  default     = "eastus2"
}

variable "secondary_location" {
  type        = string
  description = "Secondary Azure region for DR"
  default     = "centralus"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, production)"
}

variable "anf_account_id" {
  type        = string
  description = "Primary ANF account ID for replication"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# Recovery Services Vault for backups
resource "azurerm_recovery_services_vault" "ants" {
  name                = "rsv-ants-${var.environment}"
  location            = var.primary_location
  resource_group_name = var.resource_group_name
  sku                 = "Standard"

  cross_region_restore_enabled = true
  soft_delete_enabled          = true

  tags = var.tags
}

# Backup Policy for VMs
resource "azurerm_backup_policy_vm" "default" {
  name                = "policy-vm-default"
  resource_group_name = var.resource_group_name
  recovery_vault_name = azurerm_recovery_services_vault.ants.name

  timezone = "UTC"

  backup {
    frequency = "Daily"
    time      = "02:00"
  }

  retention_daily {
    count = 7
  }

  retention_weekly {
    count    = 4
    weekdays = ["Sunday"]
  }

  retention_monthly {
    count    = 12
    weekdays = ["Sunday"]
    weeks    = ["First"]
  }

  retention_yearly {
    count    = 3
    weekdays = ["Sunday"]
    weeks    = ["First"]
    months   = ["January"]
  }
}

# Traffic Manager for global load balancing
resource "azurerm_traffic_manager_profile" "ants" {
  name                   = "tm-ants-${var.environment}"
  resource_group_name    = var.resource_group_name
  traffic_routing_method = "Priority"

  dns_config {
    relative_name = "ants-${var.environment}"
    ttl           = 60
  }

  monitor_config {
    protocol                     = "HTTPS"
    port                         = 443
    path                         = "/health"
    interval_in_seconds          = 30
    timeout_in_seconds           = 10
    tolerated_number_of_failures = 3
  }

  tags = var.tags
}

# Primary Endpoint
resource "azurerm_traffic_manager_azure_endpoint" "primary" {
  name                 = "ep-primary"
  profile_id           = azurerm_traffic_manager_profile.ants.id
  priority             = 1
  weight               = 100
  target_resource_id   = var.primary_app_service_id

  # Placeholder - will be replaced with actual app service ID
  lifecycle {
    ignore_changes = [target_resource_id]
  }
}

# Secondary Endpoint
resource "azurerm_traffic_manager_azure_endpoint" "secondary" {
  name                 = "ep-secondary"
  profile_id           = azurerm_traffic_manager_profile.ants.id
  priority             = 2
  weight               = 100
  target_resource_id   = var.secondary_app_service_id

  lifecycle {
    ignore_changes = [target_resource_id]
  }
}

# Azure Front Door for global routing
resource "azurerm_cdn_frontdoor_profile" "ants" {
  name                = "afd-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"

  tags = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "api" {
  name                     = "ep-api"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.ants.id
}

# ANF Cross-Region Replication (CRR)
resource "azurerm_netapp_volume_group_sap_hana" "replication" {
  count = var.environment == "production" ? 1 : 0

  name                   = "avg-ants-replication"
  location               = var.secondary_location
  resource_group_name    = var.resource_group_name
  account_name           = "anf-ants-dr-${var.environment}"
  group_description      = "ANTS DR Replication Group"
  application_identifier = "ants"

  # Volume definitions would go here
  # Placeholder for actual volume configuration
}

# Cosmos DB with Multi-Region Write
resource "azurerm_cosmosdb_account" "ants" {
  name                = "cosmos-ants-${var.environment}"
  location            = var.primary_location
  resource_group_name = var.resource_group_name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  enable_automatic_failover = true

  consistency_policy {
    consistency_level       = "Session"
    max_interval_in_seconds = 5
    max_staleness_prefix    = 100
  }

  geo_location {
    location          = var.primary_location
    failover_priority = 0
    zone_redundant    = true
  }

  geo_location {
    location          = var.secondary_location
    failover_priority = 1
    zone_redundant    = true
  }

  backup {
    type                = "Continuous"
    tier                = "Continuous7Days"
  }

  tags = var.tags
}

# Variables for endpoint configuration
variable "primary_app_service_id" {
  type        = string
  description = "Primary app service ID"
  default     = ""
}

variable "secondary_app_service_id" {
  type        = string
  description = "Secondary app service ID"
  default     = ""
}

# Outputs
output "recovery_vault_id" {
  value = azurerm_recovery_services_vault.ants.id
}

output "traffic_manager_fqdn" {
  value = azurerm_traffic_manager_profile.ants.fqdn
}

output "front_door_endpoint" {
  value = azurerm_cdn_frontdoor_endpoint.api.host_name
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.ants.endpoint
}
