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

# Volume - Procedural Memory (Premium)
resource "azurerm_netapp_volume" "procedural" {
  name                = "vol-procedural"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "procedural"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 1024

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

# Volume - Agent Lightning Experience Buffer (Ultra)
resource "azurerm_netapp_volume" "learning_experience" {
  name                = "vol-learning-exp"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.ultra.name
  volume_path         = "learning/experience"
  service_level       = "Ultra"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 1024
  throughput_in_mibps = 1024

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = merge(var.tags, {
    component = "agent_lightning"
    data_type = "experience_buffer"
  })
}

# Volume - Agent Lightning Policy Checkpoints (Premium)
resource "azurerm_netapp_volume" "learning_policy" {
  name                = "vol-learning-policy"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "learning/policy"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 512

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = merge(var.tags, {
    component = "agent_lightning"
    data_type = "policy_checkpoints"
  })
}

# Volume - Data Lakehouse Bronze (Standard)
resource "azurerm_netapp_volume" "lakehouse_bronze" {
  name                = "vol-lakehouse-bronze"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.standard.name
  volume_path         = "lakehouse/bronze"
  service_level       = "Standard"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 10240  # 10 TB

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = merge(var.tags, {
    component = "data_lakehouse"
    tier      = "bronze"
  })
}

# Volume - Data Lakehouse Silver (Premium)
resource "azurerm_netapp_volume" "lakehouse_silver" {
  name                = "vol-lakehouse-silver"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "lakehouse/silver"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 5120  # 5 TB

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = merge(var.tags, {
    component = "data_lakehouse"
    tier      = "silver"
  })
}

# Volume - Data Lakehouse Gold (Premium)
resource "azurerm_netapp_volume" "lakehouse_gold" {
  name                = "vol-lakehouse-gold"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name
  volume_path         = "lakehouse/gold"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 2048  # 2 TB

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = true
  }

  tags = merge(var.tags, {
    component = "data_lakehouse"
    tier      = "gold"
  })
}

# Volume - Audit Receipts (Premium for fast writes)
resource "azurerm_netapp_volume" "receipts" {
  name                = "vol-receipts"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.ants.name
  pool_name           = azurerm_netapp_pool.premium.name  # Changed to Premium for compliance
  volume_path         = "receipts"
  service_level       = "Premium"
  subnet_id           = var.anf_subnet_id
  storage_quota_in_gb = 4096

  protocols = ["NFSv4.1"]

  export_policy_rule {
    rule_index          = 1
    allowed_clients     = ["0.0.0.0/0"]
    protocols_enabled   = ["NFSv4.1"]
    unix_read_write     = true
    root_access_enabled = false  # Read-only after write
  }

  tags = merge(var.tags, {
    component = "audit"
    immutable = "true"
  })
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
    # Memory Substrate
    models = {
      id         = azurerm_netapp_volume.models.id
      mount_path = azurerm_netapp_volume.models.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.models.volume_path
      tier       = "ultra"
    }
    episodic = {
      id         = azurerm_netapp_volume.episodic.id
      mount_path = azurerm_netapp_volume.episodic.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.episodic.volume_path
      tier       = "premium"
    }
    semantic = {
      id         = azurerm_netapp_volume.semantic.id
      mount_path = azurerm_netapp_volume.semantic.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.semantic.volume_path
      tier       = "premium"
    }
    procedural = {
      id         = azurerm_netapp_volume.procedural.id
      mount_path = azurerm_netapp_volume.procedural.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.procedural.volume_path
      tier       = "premium"
    }

    # Agent Lightning
    learning_experience = {
      id         = azurerm_netapp_volume.learning_experience.id
      mount_path = azurerm_netapp_volume.learning_experience.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.learning_experience.volume_path
      tier       = "ultra"
    }
    learning_policy = {
      id         = azurerm_netapp_volume.learning_policy.id
      mount_path = azurerm_netapp_volume.learning_policy.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.learning_policy.volume_path
      tier       = "premium"
    }

    # Data Lakehouse
    lakehouse_bronze = {
      id         = azurerm_netapp_volume.lakehouse_bronze.id
      mount_path = azurerm_netapp_volume.lakehouse_bronze.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.lakehouse_bronze.volume_path
      tier       = "standard"
    }
    lakehouse_silver = {
      id         = azurerm_netapp_volume.lakehouse_silver.id
      mount_path = azurerm_netapp_volume.lakehouse_silver.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.lakehouse_silver.volume_path
      tier       = "premium"
    }
    lakehouse_gold = {
      id         = azurerm_netapp_volume.lakehouse_gold.id
      mount_path = azurerm_netapp_volume.lakehouse_gold.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.lakehouse_gold.volume_path
      tier       = "premium"
    }

    # Audit
    receipts = {
      id         = azurerm_netapp_volume.receipts.id
      mount_path = azurerm_netapp_volume.receipts.mount_ip_addresses[0]
      path       = azurerm_netapp_volume.receipts.volume_path
      tier       = "premium"
    }
  }
}

output "snapshot_policy_id" {
  value = azurerm_netapp_snapshot_policy.default.id
}

output "mount_commands" {
  value = {
    models              = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.models.mount_ip_addresses[0]}:/${azurerm_netapp_volume.models.volume_path} /mnt/anf/models"
    episodic            = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.episodic.mount_ip_addresses[0]}:/${azurerm_netapp_volume.episodic.volume_path} /mnt/anf/memory/episodic"
    semantic            = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.semantic.mount_ip_addresses[0]}:/${azurerm_netapp_volume.semantic.volume_path} /mnt/anf/memory/semantic"
    procedural          = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.procedural.mount_ip_addresses[0]}:/${azurerm_netapp_volume.procedural.volume_path} /mnt/anf/memory/procedural"
    learning_experience = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.learning_experience.mount_ip_addresses[0]}:/${azurerm_netapp_volume.learning_experience.volume_path} /mnt/anf/learning/experience"
    learning_policy     = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.learning_policy.mount_ip_addresses[0]}:/${azurerm_netapp_volume.learning_policy.volume_path} /mnt/anf/learning/policy"
    lakehouse_bronze    = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.lakehouse_bronze.mount_ip_addresses[0]}:/${azurerm_netapp_volume.lakehouse_bronze.volume_path} /mnt/anf/lakehouse/bronze"
    lakehouse_silver    = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.lakehouse_silver.mount_ip_addresses[0]}:/${azurerm_netapp_volume.lakehouse_silver.volume_path} /mnt/anf/lakehouse/silver"
    lakehouse_gold      = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.lakehouse_gold.mount_ip_addresses[0]}:/${azurerm_netapp_volume.lakehouse_gold.volume_path} /mnt/anf/lakehouse/gold"
    receipts            = "mount -t nfs -o rw,hard,rsize=1048576,wsize=1048576,vers=4.1 ${azurerm_netapp_volume.receipts.mount_ip_addresses[0]}:/${azurerm_netapp_volume.receipts.volume_path} /mnt/anf/audit/receipts"
  }
  description = "NFS mount commands for all volumes"
}
