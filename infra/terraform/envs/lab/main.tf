# Capital Markets ANTS - Lab Environment Infrastructure
# Root module for lab deployment on Azure
# Smaller sizing than production for cost efficiency while maintaining architecture
# Last Updated: 2025-03-04

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.75"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment to store state in Azure Storage for persistence
  # backend "azurerm" {
  #   resource_group_name  = "terraform-state"
  #   storage_account_name = "tfstate"
  #   container_name       = "ants-lab"
  #   key                  = "terraform.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

# Local values for consistency
locals {
  resource_prefix = "ants"
  environment     = var.environment
  location        = var.location

  tags = {
    Environment = var.environment
    Project     = var.project
    Flavor      = var.flavor
    ManagedBy   = "Terraform"
    CreatedAt   = timestamp()
  }
}

# Random suffix for unique resource names
resource "random_string" "resource_suffix" {
  length  = 4
  special = false
  lower   = true
}

# ============================================================================
# AKS Cluster Module
# ============================================================================
module "aks" {
  source = "../../modules/aks"

  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment

  cluster_name       = "${local.resource_prefix}-aks-${var.environment}"
  kubernetes_version = var.kubernetes_version

  # Lab sizing: 3 nodes, Standard_D4s_v3 (smaller than production)
  node_pools = {
    system = {
      vm_size         = "Standard_D4s_v3"        # Lab: D4s (vs production D8s_v5)
      node_count      = 3
      min_count       = 3
      max_count       = 3                        # Fixed size for lab
      zones           = ["1", "2", "3"]
      os_disk_size_gb = 128
      labels          = { role = "system" }
      taints          = []
    }
    agents = {
      vm_size         = "Standard_D4s_v3"        # Lab: D4s
      node_count      = 0                        # Don't use agent pool for lab
      min_count       = 0
      max_count       = 0
      zones           = ["1"]                    # Single zone for lab
      os_disk_size_gb = 128
      labels          = { role = "agents" }
      taints          = []
    }
    gpu = {
      vm_size         = "Standard_NC6s_v3"       # Single GPU node if needed
      node_count      = 0                        # Disabled for lab
      min_count       = 0
      max_count       = 0
      zones           = ["1"]
      os_disk_size_gb = 256
      labels          = { role = "gpu", "nvidia.com/gpu" = "true" }
      taints          = ["nvidia.com/gpu=present:NoSchedule"]
    }
  }

  vnet_subnet_id = var.aks_subnet_id

  tags = local.tags
}

# ============================================================================
# Azure NetApp Files Module
# ============================================================================
module "anf" {
  source = "../../modules/anf"

  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment

  anf_subnet_id = var.anf_subnet_id

  tags = local.tags
}

# ============================================================================
# Security Module (Key Vault, Managed Identities, NSGs)
# ============================================================================
module "security" {
  source = "../../modules/security"

  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment
  tenant_id           = var.tenant_id

  vnet_id  = var.vnet_id
  subnet_id = var.aks_subnet_id

  enable_purge_protection = false               # Lab: disable for easier cleanup
  key_vault_sku           = "standard"          # Lab: standard SKU

  log_analytics_workspace_id = module.aks.log_analytics_workspace_id

  tags = local.tags
}

# ============================================================================
# PostgreSQL Database Module
# ============================================================================
module "postgresql" {
  source = "../../modules/postgresql"

  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = var.environment

  server_name              = "${local.resource_prefix}-pg-${var.environment}-${random_string.resource_suffix.result}"
  administrator_login      = var.postgres_admin_username
  administrator_password   = var.postgres_admin_password
  database_name            = "capital_markets"

  # Lab sizing: single instance, burstable
  sku_name                 = "B_Standard_B1ms"  # Lab: burstable tier
  storage_mb               = 51200               # 50GB for lab
  backup_retention_days    = 7                   # Lab: 7 days

  # Lab: minimal backup/HA configuration
  geo_redundant_backup_enabled = false
  auto_grow_enabled           = true

  tags = local.tags
}

# ============================================================================
# Key Vault Secrets (PostgreSQL credentials)
# ============================================================================
resource "azurerm_key_vault_secret" "postgres_password" {
  name            = "postgres-password"
  value           = var.postgres_admin_password
  key_vault_id    = module.security.key_vault_id
  not_before_date = timeadd(timestamp(), "-30s")

  depends_on = [module.security]
}

resource "azurerm_key_vault_secret" "postgres_username" {
  name         = "postgres-username"
  value        = var.postgres_admin_username
  key_vault_id = module.security.key_vault_id

  depends_on = [module.security]
}

resource "azurerm_key_vault_secret" "postgres_connection_string" {
  name         = "postgres-connection-string"
  value        = "postgresql://${var.postgres_admin_username}:${var.postgres_admin_password}@${module.postgresql.server_fqdn}:5432/${module.postgresql.database_name}"
  key_vault_id = module.security.key_vault_id

  depends_on = [module.postgresql, module.security]
}

# ============================================================================
# Container Registry (for agent images)
# ============================================================================
resource "azurerm_container_registry" "ants" {
  name                = "${local.resource_prefix}acr${var.environment}${random_string.resource_suffix.result}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Standard"              # Lab: Standard SKU

  admin_enabled       = true                     # Enable admin for lab access
  zone_redundancy_enabled = false                # Lab: no zone redundancy

  tags = local.tags
}

# Give AKS cluster access to ACR
resource "azurerm_role_assignment" "aks_to_acr" {
  scope              = azurerm_container_registry.ants.id
  role_definition_name = "AcrPull"
  principal_id       = module.aks.cluster_managed_identity_principal_id

  depends_on = [module.aks]
}

# ============================================================================
# Storage Account for Log Analytics
# ============================================================================
resource "azurerm_storage_account" "diagnostic_logs" {
  name                     = "${local.resource_prefix}logs${var.environment}${random_string.resource_suffix.result}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"               # Lab: local redundancy only

  depends_on = [module.aks]

  tags = local.tags
}

# ============================================================================
# Azure Monitor Action Group (for alerts)
# ============================================================================
resource "azurerm_monitor_action_group" "ants_alerts" {
  name                = "${local.resource_prefix}-alerts-${var.environment}"
  resource_group_name = var.resource_group_name
  short_name          = "ants-lab"

  # Email notification (optional - configure with your email)
  # email_receiver {
  #   name           = "sendtoadmin"
  #   email_address  = "admin@example.com"
  # }

  tags = local.tags
}

# ============================================================================
# Outputs
# ============================================================================
output "cluster_info" {
  description = "AKS cluster information"
  value = {
    cluster_name              = module.aks.cluster_name
    cluster_id                = module.aks.cluster_id
    kube_config_context       = "aks-${var.environment}"
  }
  sensitive = false
}

output "resource_group_info" {
  description = "Resource group information"
  value = {
    resource_group_name = var.resource_group_name
    location           = var.location
  }
}

output "storage_info" {
  description = "Storage and infrastructure endpoints"
  value = {
    acr_login_server              = azurerm_container_registry.ants.login_server
    postgresql_server_fqdn        = module.postgresql.server_fqdn
    key_vault_uri                 = module.security.key_vault_url
    log_analytics_workspace_id    = module.aks.log_analytics_workspace_id
  }
  sensitive = false
}

output "anf_mount_paths" {
  description = "Azure NetApp Files mount information"
  value = {
    models              = module.anf.models_mount_path
    episodic            = module.anf.episodic_mount_path
    semantic            = module.anf.semantic_mount_path
    procedural          = module.anf.procedural_mount_path
    learning_experience = module.anf.learning_experience_mount_path
    learning_policy     = module.anf.learning_policy_mount_path
    lakehouse_bronze    = module.anf.lakehouse_bronze_mount_path
    lakehouse_silver    = module.anf.lakehouse_silver_mount_path
    lakehouse_gold      = module.anf.lakehouse_gold_mount_path
    receipts            = module.anf.receipts_mount_path
  }
}

output "security_info" {
  description = "Security and identity information"
  value = {
    key_vault_name                = module.security.key_vault_name
    agents_managed_identity_id    = module.security.agents_identity_id
    agents_managed_identity_client_id = module.security.agents_identity_client_id
    aks_managed_identity_id       = module.security.aks_identity_id
    aks_managed_identity_client_id = module.security.aks_identity_client_id
    nsg_id                        = module.security.nsg_id
  }
  sensitive = false
}

output "deployment_summary" {
  description = "Quick reference for lab deployment"
  value = {
    cluster_name           = module.aks.cluster_name
    acr_registry           = azurerm_container_registry.ants.login_server
    postgres_server        = module.postgresql.server_fqdn
    key_vault_name         = module.security.key_vault_name
    next_steps = [
      "1. Configure kubectl: az aks get-credentials --resource-group ${var.resource_group_name} --name ${module.aks.cluster_name}",
      "2. Deploy Helm chart: helm install capital-markets ./infra/helm/capital-markets -f ./infra/helm/values-lab.yaml",
      "3. Verify deployment: kubectl get pods",
      "4. Check logs: kubectl logs -f deployment/trading-agent"
    ]
  }
}
