# Azure NetApp Files Module for ANTS
# Provides the memory substrate for AI agents

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, production)"
}

variable "anf_subnet_id" {
  type        = string
  description = "Subnet ID for ANF"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# ANF Account
resource "azurerm_netapp_account" "ants" {
  name                = "anf-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# Ultra Pool - For model cache and inference
resource "azurerm_netapp_pool" "ultra" {
  name                = "pool-ultra"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Ultra"
  size_in_tb          = 4
  qos_type            = "Manual"

  tags = var.tags
}

# Premium Pool - For active agent memory
resource "azurerm_netapp_pool" "premium" {
  name                = "pool-premium"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Premium"
  size_in_tb          = 8
  qos_type            = "Auto"

  tags = var.tags
}

# Standard Pool - For archival with cool access
resource "azurerm_netapp_pool" "standard" {
  name                = "pool-standard"
  account_name        = azurerm_netapp_account.ants.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = "Standard"
  size_in_tb          = 16
  qos_type            = "Auto"

  tags = var.tags
}

# Volume - Model Cache (Ultra)
resource "azurerm_netapp_volume" "models" {
  name                = "vol-models"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.ultra.name
  volume_path         = "models"
  service_level       = "Ultra"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 2048
  throughput_in_mibps = 2048

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = var.tags
}

# Volume - Episodic Memory (Premium)
resource "azurerm_netapp_volume" "episodic" {
  name                = "vol-episodic"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "episodic"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 4096

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = var.tags
}

# Volume - Semantic Memory (Premium)
resource "azurerm_netapp_volume" "semantic" {
  name                = "vol-semantic"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "semantic"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 2048

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = var.tags
}

# Volume - Audit Receipts (Standard)
resource "azurerm_netapp_volume" "receipts" {
  name                = "vol-receipts"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.standard.name
  volume_path         = "receipts"
  service_level       = "Standard"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 8192

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = false  # Read-only after write
  }

  tags = var.tags
}

# Snapshot Policy
resource "azurerm_netapp_snapshot_policy" "default" {
  name                = "policy-default"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  enabled             = true

  hourly_schedule {
    snapshots_to_keep = 24
    minute            = 0
  }

  daily_schedule {
    snapshots_to_keep = 7
    hour              = 2
    minute            = 0
  }

  weekly_schedule {
    snapshots_to_keep = 4
    days_of_week      = ["Sunday"]
    hour              = 3
    minute            = 0
  }

  tags = var.tags
}

# Outputs
output "account_name" {
  value = azurerm_netapp_account.ants.name
}

output "volumes" {
  value = {
    models = {
      id         = azurerm_netapp_volume.models.id
      mount_path = azurerm_netapp_volume.models.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.models.volume_path
    }
    episodic = {
      id         = azurerm_netapp_volume.episodic.id
      mount_path = azurerm_netapp_volume.episodic.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.episodic.volume_path
    }
    semantic = {
      id         = azurerm_netapp_volume.semantic.id
      mount_path = azurerm_netapp_volume.semantic.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.semantic.volume_path
    }
    receipts = {
      id         = azurerm_netapp_volume.receipts.id
      mount_path = azurerm_netapp_volume.receipts.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.receipts.volume_path
    }
  }
}
