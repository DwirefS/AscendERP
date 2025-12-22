# Azure Databricks Module for ANTS
# Unity Catalog integration with Delta Lake and MLflow

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

variable "vnet_id" {
  type        = string
  description = "Virtual network ID"
}

variable "private_subnet_name" {
  type        = string
  description = "Private subnet name for Databricks"
}

variable "public_subnet_name" {
  type        = string
  description = "Public subnet name for Databricks"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# Databricks Workspace
resource "azurerm_databricks_workspace" "ants" {
  name                = "dbw-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "premium"

  managed_resource_group_name = "rg-dbw-ants-${var.environment}-managed"

  custom_parameters {
    no_public_ip                                         = true
    virtual_network_id                                   = var.vnet_id
    private_subnet_name                                  = var.private_subnet_name
    public_subnet_name                                   = var.public_subnet_name
    private_subnet_network_security_group_association_id = azurerm_subnet_network_security_group_association.private.id
    public_subnet_network_security_group_association_id  = azurerm_subnet_network_security_group_association.public.id
  }

  tags = var.tags
}

# Network Security Group for Databricks
resource "azurerm_network_security_group" "databricks" {
  name                = "nsg-dbw-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = var.tags
}

# NSG Association - Private Subnet
resource "azurerm_subnet_network_security_group_association" "private" {
  subnet_id                 = data.azurerm_subnet.private.id
  network_security_group_id = azurerm_network_security_group.databricks.id
}

# NSG Association - Public Subnet
resource "azurerm_subnet_network_security_group_association" "public" {
  subnet_id                 = data.azurerm_subnet.public.id
  network_security_group_id = azurerm_network_security_group.databricks.id
}

# Data sources for subnets
data "azurerm_subnet" "private" {
  name                 = var.private_subnet_name
  virtual_network_name = data.azurerm_virtual_network.vnet.name
  resource_group_name  = var.resource_group_name
}

data "azurerm_subnet" "public" {
  name                 = var.public_subnet_name
  virtual_network_name = data.azurerm_virtual_network.vnet.name
  resource_group_name  = var.resource_group_name
}

data "azurerm_virtual_network" "vnet" {
  resource_group_name = var.resource_group_name
  name                = split("/", var.vnet_id)[8]
}

# Databricks Access Connector for Unity Catalog
resource "azurerm_databricks_access_connector" "unity" {
  name                = "dbac-ants-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# Storage Account for Unity Catalog Metastore
resource "azurerm_storage_account" "unity" {
  name                     = "stdbwunity${var.environment}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  is_hns_enabled           = true  # Required for Unity Catalog

  tags = var.tags
}

# Unity Catalog Container
resource "azurerm_storage_container" "unity" {
  name                  = "unity-catalog"
  storage_account_name  = azurerm_storage_account.unity.name
  container_access_type = "private"
}

# Bronze Container (Medallion Architecture)
resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_name  = azurerm_storage_account.unity.name
  container_access_type = "private"
}

# Silver Container
resource "azurerm_storage_container" "silver" {
  name                  = "silver"
  storage_account_name  = azurerm_storage_account.unity.name
  container_access_type = "private"
}

# Gold Container
resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_name  = azurerm_storage_account.unity.name
  container_access_type = "private"
}

# Role Assignment for Access Connector
resource "azurerm_role_assignment" "unity_blob" {
  scope                = azurerm_storage_account.unity.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.unity.identity[0].principal_id
}

# Outputs
output "workspace_id" {
  value = azurerm_databricks_workspace.ants.id
}

output "workspace_url" {
  value = "https://${azurerm_databricks_workspace.ants.workspace_url}"
}

output "access_connector_id" {
  value = azurerm_databricks_access_connector.unity.id
}

output "unity_storage_account" {
  value = azurerm_storage_account.unity.name
}

output "storage_containers" {
  value = {
    unity  = azurerm_storage_container.unity.name
    bronze = azurerm_storage_container.bronze.name
    silver = azurerm_storage_container.silver.name
    gold   = azurerm_storage_container.gold.name
  }
}
