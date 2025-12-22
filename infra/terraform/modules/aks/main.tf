# Azure Kubernetes Service with HA Configuration for ANTS
# Multi-zone deployment with auto-scaling

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

variable "cluster_name" {
  type        = string
  description = "AKS cluster name"
  default     = "aks-ants"
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version"
  default     = "1.29"
}

variable "node_pools" {
  type = map(object({
    vm_size         = string
    node_count      = number
    min_count       = number
    max_count       = number
    zones           = list(string)
    os_disk_size_gb = number
    labels          = map(string)
    taints          = list(string)
  }))
  default = {
    system = {
      vm_size         = "Standard_D4s_v5"
      node_count      = 3
      min_count       = 3
      max_count       = 5
      zones           = ["1", "2", "3"]
      os_disk_size_gb = 128
      labels          = { "role" = "system" }
      taints          = []
    }
    agents = {
      vm_size         = "Standard_D8s_v5"
      node_count      = 3
      min_count       = 3
      max_count       = 20
      zones           = ["1", "2", "3"]
      os_disk_size_gb = 256
      labels          = { "role" = "agents" }
      taints          = []
    }
    gpu = {
      vm_size         = "Standard_NC24ads_A100_v4"
      node_count      = 0
      min_count       = 0
      max_count       = 10
      zones           = ["1", "2", "3"]
      os_disk_size_gb = 512
      labels          = { "role" = "gpu", "nvidia.com/gpu" = "true" }
      taints          = ["nvidia.com/gpu=present:NoSchedule"]
    }
  }
}

variable "vnet_subnet_id" {
  type        = string
  description = "Subnet ID for AKS nodes"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "ants" {
  name                = "${var.cluster_name}-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "ants-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  default_node_pool {
    name                = "system"
    vm_size             = var.node_pools.system.vm_size
    node_count          = var.node_pools.system.node_count
    min_count           = var.node_pools.system.min_count
    max_count           = var.node_pools.system.max_count
    zones               = var.node_pools.system.zones
    os_disk_size_gb     = var.node_pools.system.os_disk_size_gb
    vnet_subnet_id      = var.vnet_subnet_id
    auto_scaling_enabled = true
    node_labels         = var.node_pools.system.labels
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    managed            = true
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.ants.id
  }

  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  workload_autoscaler_profile {
    keda_enabled = true
  }

  tags = var.tags
}

# Agent Node Pool
resource "azurerm_kubernetes_cluster_node_pool" "agents" {
  name                  = "agents"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.ants.id
  vm_size               = var.node_pools.agents.vm_size
  node_count            = var.node_pools.agents.node_count
  min_count             = var.node_pools.agents.min_count
  max_count             = var.node_pools.agents.max_count
  zones                 = var.node_pools.agents.zones
  os_disk_size_gb       = var.node_pools.agents.os_disk_size_gb
  vnet_subnet_id        = var.vnet_subnet_id
  auto_scaling_enabled  = true
  node_labels           = var.node_pools.agents.labels

  tags = var.tags
}

# GPU Node Pool
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.ants.id
  vm_size               = var.node_pools.gpu.vm_size
  node_count            = var.node_pools.gpu.node_count
  min_count             = var.node_pools.gpu.min_count
  max_count             = var.node_pools.gpu.max_count
  zones                 = var.node_pools.gpu.zones
  os_disk_size_gb       = var.node_pools.gpu.os_disk_size_gb
  vnet_subnet_id        = var.vnet_subnet_id
  auto_scaling_enabled  = true
  node_labels           = var.node_pools.gpu.labels
  node_taints           = var.node_pools.gpu.taints

  tags = var.tags
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "ants" {
  name                = "law-ants-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

# Outputs
output "cluster_id" {
  value = azurerm_kubernetes_cluster.ants.id
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.ants.name
}

output "kube_config" {
  value     = azurerm_kubernetes_cluster.ants.kube_config_raw
  sensitive = true
}

output "host" {
  value     = azurerm_kubernetes_cluster.ants.kube_config[0].host
  sensitive = true
}

output "identity" {
  value = azurerm_kubernetes_cluster.ants.identity[0].principal_id
}
