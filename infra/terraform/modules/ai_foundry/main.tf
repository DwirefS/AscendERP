# Azure AI Foundry Module for ANTS
# Integrates Azure AI Services, Model Catalog, and Prompt Flow

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

variable "key_vault_id" {
  type        = string
  description = "Key Vault ID for secrets"
}

variable "storage_account_id" {
  type        = string
  description = "Storage account ID for AI artifacts"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# Azure AI Hub (AI Foundry Project)
resource "azurerm_ai_services" "ants" {
  name                = "ai-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "S0"

  custom_subdomain_name = "ants-ai-${var.environment}"

  network_acls {
    default_action = "Allow"
  }

  tags = var.tags
}

# Azure Machine Learning Workspace (AI Hub)
resource "azurerm_machine_learning_workspace" "ants" {
  name                          = "mlw-ants-${var.environment}"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  application_insights_id       = azurerm_application_insights.ants.id
  key_vault_id                  = var.key_vault_id
  storage_account_id            = var.storage_account_id
  container_registry_id         = azurerm_container_registry.ants.id
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# Application Insights for monitoring
resource "azurerm_application_insights" "ants" {
  name                = "appi-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = "web"

  tags = var.tags
}

# Container Registry for model containers
resource "azurerm_container_registry" "ants" {
  name                = "crANTS${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Premium"
  admin_enabled       = false

  georeplications {
    location                = "centralus"
    zone_redundancy_enabled = true
  }

  tags = var.tags
}

# Azure OpenAI Service
resource "azurerm_cognitive_account" "openai" {
  name                = "oai-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  kind                = "OpenAI"
  sku_name            = "S0"

  custom_subdomain_name = "ants-openai-${var.environment}"

  network_acls {
    default_action = "Allow"
  }

  tags = var.tags
}

# GPT-4 Deployment
resource "azurerm_cognitive_deployment" "gpt4" {
  name                 = "gpt-4-turbo"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4"
    version = "turbo-2024-04-09"
  }

  sku {
    name     = "Standard"
    capacity = 30
  }
}

# Text Embedding Deployment
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = 120
  }
}

# Prompt Flow Compute
resource "azurerm_machine_learning_compute_instance" "promptflow" {
  name                          = "ci-promptflow-${var.environment}"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.ants.id
  virtual_machine_size          = "Standard_DS3_v2"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# AI Search for RAG
resource "azurerm_search_service" "ants" {
  name                = "srch-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "standard"
  replica_count       = 2
  partition_count     = 1

  semantic_search_sku = "standard"

  tags = var.tags
}

# Outputs
output "ai_services_endpoint" {
  value = azurerm_ai_services.ants.endpoint
}

output "ml_workspace_id" {
  value = azurerm_machine_learning_workspace.ants.id
}

output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "openai_key" {
  value     = azurerm_cognitive_account.openai.primary_access_key
  sensitive = true
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.ants.name}.search.windows.net"
}

output "container_registry" {
  value = azurerm_container_registry.ants.login_server
}
