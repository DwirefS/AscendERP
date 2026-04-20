# Capital Markets ANTS - Lab Environment Variables
# All variables with descriptions, types, and safe defaults where applicable
# Sensitive variables (credentials, keys) have no defaults
# Last Updated: 2025-03-04

# ============================================================================
# Azure Subscription and Authentication
# ============================================================================

variable "subscription_id" {
  type        = string
  description = "Azure Subscription ID"
  sensitive   = true
  # No default - must be provided
}

variable "tenant_id" {
  type        = string
  description = "Azure AD Tenant ID"
  sensitive   = true
  # No default - must be provided
}

variable "client_id" {
  type        = string
  description = "Service Principal Client ID (optional, uses current account if not specified)"
  sensitive   = true
  default     = ""
}

variable "client_secret" {
  type        = string
  description = "Service Principal Client Secret (optional)"
  sensitive   = true
  default     = ""
}

# ============================================================================
# Resource Group and Location
# ============================================================================

variable "resource_group_name" {
  type        = string
  description = "Name of the Azure resource group for lab resources"
  default     = "ants-capital-markets-lab"

  validation {
    condition     = length(var.resource_group_name) > 0 && length(var.resource_group_name) <= 90
    error_message = "Resource group name must be between 1 and 90 characters."
  }
}

variable "location" {
  type        = string
  description = "Azure region for resource deployment (e.g., eastus, westus2, northeurope)"
  default     = "eastus"

  validation {
    condition     = contains(["eastus", "westus2", "northeurope", "westeurope", "canadacentral", "southeastasia"], var.location)
    error_message = "Location must be a valid Azure region."
  }
}

# ============================================================================
# Environment Configuration
# ============================================================================

variable "environment" {
  type        = string
  description = "Environment name (lab, dev, staging, production)"
  default     = "lab"

  validation {
    condition     = contains(["lab", "dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: lab, dev, staging, production"
  }
}

variable "project" {
  type        = string
  description = "Project name for tagging"
  default     = "ants"
}

variable "flavor" {
  type        = string
  description = "Flavor/use case (capital-markets, insurance, supply-chain, etc.)"
  default     = "capital-markets"
}

# ============================================================================
# Networking
# ============================================================================

variable "vnet_id" {
  type        = string
  description = "Virtual Network ID for AKS and ANF"
  # Must be provided or should be created separately
}

variable "vnet_name" {
  type        = string
  description = "Virtual Network name"
  default     = "vnet-ants-lab"
}

variable "aks_subnet_id" {
  type        = string
  description = "Subnet ID for AKS nodes"
  # Must be provided
}

variable "aks_subnet_name" {
  type        = string
  description = "Subnet name for AKS"
  default     = "subnet-aks"
}

variable "anf_subnet_id" {
  type        = string
  description = "Subnet ID for Azure NetApp Files (must have Microsoft.NetApp/volumes delegation)"
  # Must be provided
}

variable "anf_subnet_name" {
  type        = string
  description = "Subnet name for ANF"
  default     = "subnet-anf"
}

# ============================================================================
# AKS Cluster Configuration
# ============================================================================

variable "cluster_name" {
  type        = string
  description = "Name of the AKS cluster"
  default     = "aks-ants-lab"

  validation {
    condition     = length(var.cluster_name) >= 1 && length(var.cluster_name) <= 63
    error_message = "Cluster name must be 1-63 characters."
  }
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version to deploy (e.g., 1.29, 1.30)"
  default     = "1.29"

  validation {
    condition     = can(regex("^1\\.\\d+$", var.kubernetes_version))
    error_message = "Kubernetes version must be in format like 1.29 or 1.30"
  }
}

variable "aks_node_count" {
  type        = number
  description = "Number of AKS nodes for system pool (lab: 3, production: 3-5)"
  default     = 3

  validation {
    condition     = var.aks_node_count >= 1 && var.aks_node_count <= 10
    error_message = "Node count must be between 1 and 10 for lab environment."
  }
}

variable "aks_vm_size" {
  type        = string
  description = "VM size for AKS nodes (lab: Standard_D4s_v3, prod: Standard_D8s_v5)"
  default     = "Standard_D4s_v3"

  validation {
    condition     = can(regex("^Standard_", var.aks_vm_size))
    error_message = "VM size must be a valid Azure VM size (e.g., Standard_D4s_v3)."
  }
}

variable "aks_enable_autoscaling" {
  type        = bool
  description = "Enable AKS autoscaling (disabled for lab to control costs)"
  default     = false
}

variable "aks_max_node_count" {
  type        = number
  description = "Maximum number of nodes if autoscaling enabled"
  default     = 5
}

# ============================================================================
# Azure NetApp Files (ANF) Configuration
# ============================================================================

variable "anf_account_name" {
  type        = string
  description = "Name of the NetApp account"
  default     = "anf-ants-lab"
}

variable "anf_enable_snapshots" {
  type        = bool
  description = "Enable ANF snapshot policies for backups"
  default     = true
}

variable "anf_pool_size_tb" {
  type        = number
  description = "Total size of ANF pools in TB (lab: 1TB for all tiers, production: 28TB)"
  default     = 1

  validation {
    condition     = var.anf_pool_size_tb >= 1 && var.anf_pool_size_tb <= 500
    error_message = "ANF pool size must be between 1 and 500 TB."
  }
}

variable "anf_volume_quota_gb" {
  type        = number
  description = "Size of individual ANF volumes in GB (lab: 100GB per volume)"
  default     = 100

  validation {
    condition     = var.anf_volume_quota_gb >= 10 && var.anf_volume_quota_gb <= 102400
    error_message = "Volume quota must be between 10GB and 100TB."
  }
}

# ============================================================================
# PostgreSQL Database Configuration
# ============================================================================

variable "postgres_server_name" {
  type        = string
  description = "Name of PostgreSQL server (will be suffixed with random string)"
  default     = "pg-ants-lab"
}

variable "postgres_admin_username" {
  type        = string
  description = "PostgreSQL administrator username"
  default     = "antsadmin"

  validation {
    condition     = length(var.postgres_admin_username) >= 1 && length(var.postgres_admin_username) <= 63
    error_message = "PostgreSQL username must be 1-63 characters."
  }
}

variable "postgres_admin_password" {
  type        = string
  description = "PostgreSQL administrator password (must be strong)"
  sensitive   = true
  # No default - must be provided

  validation {
    condition     = length(var.postgres_admin_password) >= 8
    error_message = "PostgreSQL password must be at least 8 characters."
  }
}

variable "postgres_sku" {
  type        = string
  description = "PostgreSQL SKU (lab: B_Standard_B1ms, production: GP_Standard_D4s_v3)"
  default     = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  type        = number
  description = "PostgreSQL storage size in MB (lab: 50GB, production: 256GB+)"
  default     = 51200

  validation {
    condition     = var.postgres_storage_mb >= 32768 && var.postgres_storage_mb <= 4194304
    error_message = "PostgreSQL storage must be between 32GB and 4TB."
  }
}

variable "postgres_backup_retention_days" {
  type        = number
  description = "Backup retention in days (lab: 7, production: 30)"
  default     = 7

  validation {
    condition     = var.postgres_backup_retention_days >= 1 && var.postgres_backup_retention_days <= 35
    error_message = "Backup retention must be between 1 and 35 days."
  }
}

variable "postgres_geo_redundant" {
  type        = bool
  description = "Enable geo-redundant backups (lab: false, production: true)"
  default     = false
}

# ============================================================================
# Container Registry Configuration
# ============================================================================

variable "acr_sku" {
  type        = string
  description = "Azure Container Registry SKU (lab: Standard, production: Premium)"
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.acr_sku)
    error_message = "ACR SKU must be Basic, Standard, or Premium."
  }
}

variable "acr_admin_enabled" {
  type        = bool
  description = "Enable admin user for ACR (not recommended for production)"
  default     = true
}

# ============================================================================
# Monitoring and Logging Configuration
# ============================================================================

variable "log_analytics_retention_days" {
  type        = number
  description = "Log Analytics retention in days (lab: 30, production: 90)"
  default     = 30

  validation {
    condition     = var.log_analytics_retention_days >= 1 && var.log_analytics_retention_days <= 730
    error_message = "Log retention must be between 1 and 730 days."
  }
}

variable "enable_diagnostics" {
  type        = bool
  description = "Enable diagnostics logging for all resources"
  default     = true
}

variable "enable_monitoring" {
  type        = bool
  description = "Enable monitoring alerts and dashboards"
  default     = false  # Disabled by default in lab to reduce costs
}

# ============================================================================
# Security Configuration
# ============================================================================

variable "enable_key_vault_purge_protection" {
  type        = bool
  description = "Enable Key Vault purge protection (lab: false, production: true)"
  default     = false
}

variable "enable_key_vault_rbac" {
  type        = bool
  description = "Use RBAC for Key Vault access (recommended)"
  default     = true
}

variable "key_vault_sku" {
  type        = string
  description = "Key Vault SKU (lab: standard, production: premium)"
  default     = "standard"

  validation {
    condition     = contains(["standard", "premium"], var.key_vault_sku)
    error_message = "Key Vault SKU must be standard or premium."
  }
}

# ============================================================================
# Tags
# ============================================================================

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default = {
    managed_by  = "terraform"
    cost_center = "engineering"
  }
}

variable "custom_tags" {
  type        = map(string)
  description = "Custom tags for organization-specific requirements"
  default     = {}
}

# ============================================================================
# Feature Flags
# ============================================================================

variable "enable_gpu_pool" {
  type        = bool
  description = "Enable GPU node pool for optional GPU workloads (lab: false)"
  default     = false
}

variable "enable_network_policy" {
  type        = bool
  description = "Enable Calico network policies (recommended for production)"
  default     = false  # Disabled for lab to simplify troubleshooting
}

variable "enable_pod_security_policy" {
  type        = bool
  description = "Enable pod security policy (deprecated, use pod security standards)"
  default     = false
}

variable "enable_workload_identity" {
  type        = bool
  description = "Enable Workload Identity for pod authentication to Azure services"
  default     = true
}

# ============================================================================
# Deployment Configuration
# ============================================================================

variable "prevent_resource_destruction" {
  type        = bool
  description = "Add lifecycle rules to prevent accidental resource destruction"
  default     = false  # Lab: allow destruction; production: true
}

variable "deployment_timestamp" {
  type        = string
  description = "Timestamp for deployment tracking (auto-generated)"
  default     = ""
}
