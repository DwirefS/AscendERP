# Security Module
#
# Configures security infrastructure:
# - Azure Key Vault for secrets
# - Managed Identities
# - Network Security Groups
# - Private Endpoints
# - Azure Defender

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "vnet_id" {
  description = "Virtual network ID for private endpoints"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for private endpoints"
  type        = string
}

variable "enable_purge_protection" {
  description = "Enable purge protection for Key Vault (recommended for prod)"
  type        = bool
  default     = true
}

variable "key_vault_sku" {
  description = "Key Vault SKU (standard or premium)"
  type        = string
  default     = "standard"
}

# Azure Key Vault for secrets management
resource "azurerm_key_vault" "ants" {
  name                = "ants-kv-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  sku_name            = var.key_vault_sku

  # Security settings
  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = false
  enable_rbac_authorization       = true  # Use RBAC instead of access policies
  purge_protection_enabled        = var.enable_purge_protection
  soft_delete_retention_days      = 90

  # Network security
  network_acls {
    bypass         = "AzureServices"
    default_action = "Deny"  # Deny all traffic by default

    # Allow specific IP ranges (configure as needed)
    # ip_rules = var.allowed_ip_ranges

    # Allow access from specific virtual networks
    virtual_network_subnet_ids = [var.subnet_id]
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "ANTS Secrets Management"
  }
}

# Private endpoint for Key Vault
resource "azurerm_private_endpoint" "key_vault" {
  name                = "ants-kv-pe-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "ants-kv-psc"
    private_connection_resource_id = azurerm_key_vault.ants.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Managed Identity for AKS cluster
resource "azurerm_user_assigned_identity" "aks" {
  name                = "ants-aks-identity-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Managed Identity for agents
resource "azurerm_user_assigned_identity" "agents" {
  name                = "ants-agents-identity-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "ANTS Agents Runtime Identity"
  }
}

# Key Vault RBAC: Grant agents identity access to secrets
resource "azurerm_role_assignment" "agents_kv_secrets" {
  scope                = azurerm_key_vault.ants.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.agents.principal_id
}

# Network Security Group for agent workloads
resource "azurerm_network_security_group" "agents" {
  name                = "ants-agents-nsg-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  # Allow HTTPS inbound (for API gateway)
  security_rule {
    name                       = "AllowHTTPS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Allow HTTP inbound (for health checks)
  security_rule {
    name                       = "AllowHTTP"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
  }

  # Deny all other inbound traffic
  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Allow outbound to Azure services
  security_rule {
    name                       = "AllowAzureServices"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "AzureCloud"
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Azure Defender for Key Vault
resource "azurerm_security_center_subscription_pricing" "key_vault" {
  tier          = "Standard"
  resource_type = "KeyVaults"
}

# Azure Defender for Kubernetes
resource "azurerm_security_center_subscription_pricing" "kubernetes" {
  tier          = "Standard"
  resource_type = "KubernetesService"
}

# Azure Defender for Storage
resource "azurerm_security_center_subscription_pricing" "storage" {
  tier          = "Standard"
  resource_type = "StorageAccounts"
}

# Diagnostic settings for Key Vault (audit logging)
resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  name                       = "ants-kv-diagnostics"
  target_resource_id         = azurerm_key_vault.ants.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "AuditEvent"

    retention_policy {
      enabled = true
      days    = 365
    }
  }

  metric {
    category = "AllMetrics"

    retention_policy {
      enabled = true
      days    = 30
    }
  }
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for diagnostics"
  type        = string
}

# Outputs
output "key_vault_id" {
  description = "Key Vault ID"
  value       = azurerm_key_vault.ants.id
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.ants.name
}

output "key_vault_url" {
  description = "Key Vault URL"
  value       = azurerm_key_vault.ants.vault_uri
}

output "aks_identity_id" {
  description = "AKS managed identity ID"
  value       = azurerm_user_assigned_identity.aks.id
}

output "aks_identity_client_id" {
  description = "AKS managed identity client ID"
  value       = azurerm_user_assigned_identity.aks.client_id
}

output "agents_identity_id" {
  description = "Agents managed identity ID"
  value       = azurerm_user_assigned_identity.agents.id
}

output "agents_identity_client_id" {
  description = "Agents managed identity client ID"
  value       = azurerm_user_assigned_identity.agents.client_id
}

output "nsg_id" {
  description = "Network security group ID"
  value       = azurerm_network_security_group.agents.id
}
