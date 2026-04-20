# Capital Markets ANTS - Lab Environment Outputs
# Exports key information for accessing deployed infrastructure
# Last Updated: 2025-03-04

# ============================================================================
# AKS Cluster Outputs
# ============================================================================

output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks.cluster_name
}

output "aks_cluster_id" {
  description = "ID of the AKS cluster"
  value       = module.aks.cluster_id
  sensitive   = true
}

output "aks_kube_config_raw" {
  description = "Raw kubeconfig for cluster access"
  value       = module.aks.kube_config_raw
  sensitive   = true
}

output "aks_kube_config_host" {
  description = "Kubernetes API server host"
  value       = module.aks.kube_config_host
  sensitive   = true
}

output "aks_node_resource_group" {
  description = "Resource group for AKS nodes"
  value       = module.aks.node_resource_group
}

output "aks_cluster_principal_id" {
  description = "Principal ID of AKS cluster identity"
  value       = module.aks.cluster_managed_identity_principal_id
}

# ============================================================================
# Resource Group Outputs
# ============================================================================

output "resource_group_name" {
  description = "Name of the resource group"
  value       = var.resource_group_name
}

output "resource_group_id" {
  description = "ID of the resource group"
  value       = "subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group_name}"
}

output "location" {
  description = "Azure region where resources are deployed"
  value       = var.location
}

# ============================================================================
# Container Registry Outputs
# ============================================================================

output "acr_login_server" {
  description = "Login server URL for container registry"
  value       = azurerm_container_registry.ants.login_server
}

output "acr_id" {
  description = "ID of container registry"
  value       = azurerm_container_registry.ants.id
}

output "acr_admin_username" {
  description = "Admin username for container registry"
  value       = azurerm_container_registry.ants.admin_username
}

output "acr_admin_password" {
  description = "Admin password for container registry (for docker login)"
  value       = azurerm_container_registry.ants.admin_password
  sensitive   = true
}

# ============================================================================
# PostgreSQL Outputs
# ============================================================================

output "postgresql_server_fqdn" {
  description = "Fully qualified domain name of PostgreSQL server"
  value       = module.postgresql.server_fqdn
}

output "postgresql_server_id" {
  description = "ID of PostgreSQL server"
  value       = module.postgresql.server_id
  sensitive   = true
}

output "postgresql_database_name" {
  description = "Name of the capital_markets database"
  value       = module.postgresql.database_name
}

output "postgresql_admin_username" {
  description = "PostgreSQL administrator username"
  value       = var.postgres_admin_username
  sensitive   = true
}

output "postgresql_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${var.postgres_admin_username}@${module.postgresql.server_fqdn}:5432/${module.postgresql.database_name}?sslmode=require"
  sensitive   = true
}

# ============================================================================
# Key Vault Outputs
# ============================================================================

output "key_vault_id" {
  description = "ID of the Key Vault"
  value       = module.security.key_vault_id
  sensitive   = true
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = module.security.key_vault_name
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = module.security.key_vault_url
}

# ============================================================================
# Managed Identity Outputs
# ============================================================================

output "aks_managed_identity_id" {
  description = "AKS managed identity ID"
  value       = module.security.aks_identity_id
}

output "aks_managed_identity_principal_id" {
  description = "AKS managed identity principal ID"
  value       = module.security.aks_identity_principal_id
  sensitive   = true
}

output "aks_managed_identity_client_id" {
  description = "AKS managed identity client ID"
  value       = module.security.aks_identity_client_id
}

output "agents_managed_identity_id" {
  description = "Agents managed identity ID"
  value       = module.security.agents_identity_id
}

output "agents_managed_identity_principal_id" {
  description = "Agents managed identity principal ID"
  value       = module.security.agents_identity_principal_id
  sensitive   = true
}

output "agents_managed_identity_client_id" {
  description = "Agents managed identity client ID"
  value       = module.security.agents_identity_client_id
}

# ============================================================================
# Network Security Outputs
# ============================================================================

output "nsg_id" {
  description = "Network Security Group ID"
  value       = module.security.nsg_id
}

output "network_interface_ids" {
  description = "Network interfaces in security group"
  value       = []  # Populated by NSG associations
}

# ============================================================================
# Azure NetApp Files Outputs
# ============================================================================

output "anf_account_name" {
  description = "Azure NetApp Files account name"
  value       = module.anf.account_name
}

output "anf_models_volume_id" {
  description = "ID of models (Ultra) volume"
  value       = module.anf.volumes["models"].id
  sensitive   = true
}

output "anf_models_mount_path" {
  description = "NFS mount path for models volume"
  value       = "nfs://${module.anf.volumes["models"].mount_path}/models"
}

output "anf_episodic_volume_id" {
  description = "ID of episodic (Premium) memory volume"
  value       = module.anf.volumes["episodic"].id
  sensitive   = true
}

output "anf_episodic_mount_path" {
  description = "NFS mount path for episodic memory volume"
  value       = "nfs://${module.anf.volumes["episodic"].mount_path}/episodic"
}

output "anf_semantic_volume_id" {
  description = "ID of semantic (Premium) memory volume"
  value       = module.anf.volumes["semantic"].id
  sensitive   = true
}

output "anf_semantic_mount_path" {
  description = "NFS mount path for semantic memory volume"
  value       = "nfs://${module.anf.volumes["semantic"].mount_path}/semantic"
}

output "anf_procedural_volume_id" {
  description = "ID of procedural (Premium) memory volume"
  value       = module.anf.volumes["procedural"].id
  sensitive   = true
}

output "anf_procedural_mount_path" {
  description = "NFS mount path for procedural memory volume"
  value       = "nfs://${module.anf.volumes["procedural"].mount_path}/procedural"
}

output "anf_learning_experience_mount_path" {
  description = "NFS mount path for Agent Lightning experience buffer"
  value       = "nfs://${module.anf.volumes["learning_experience"].mount_path}/learning/experience"
}

output "anf_learning_policy_mount_path" {
  description = "NFS mount path for Agent Lightning policy checkpoints"
  value       = "nfs://${module.anf.volumes["learning_policy"].mount_path}/learning/policy"
}

output "anf_lakehouse_bronze_mount_path" {
  description = "NFS mount path for Data Lakehouse Bronze tier"
  value       = "nfs://${module.anf.volumes["lakehouse_bronze"].mount_path}/lakehouse/bronze"
}

output "anf_lakehouse_silver_mount_path" {
  description = "NFS mount path for Data Lakehouse Silver tier"
  value       = "nfs://${module.anf.volumes["lakehouse_silver"].mount_path}/lakehouse/silver"
}

output "anf_lakehouse_gold_mount_path" {
  description = "NFS mount path for Data Lakehouse Gold tier"
  value       = "nfs://${module.anf.volumes["lakehouse_gold"].mount_path}/lakehouse/gold"
}

output "anf_receipts_mount_path" {
  description = "NFS mount path for audit receipts volume"
  value       = "nfs://${module.anf.volumes["receipts"].mount_path}/receipts"
}

output "anf_snapshot_policy_id" {
  description = "ID of ANF snapshot policy"
  value       = module.anf.snapshot_policy_id
  sensitive   = true
}

output "anf_mount_commands" {
  description = "NFS mount commands for all ANF volumes"
  value       = module.anf.mount_commands
}

# ============================================================================
# Monitoring and Logging Outputs
# ============================================================================

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = module.aks.log_analytics_workspace_id
  sensitive   = true
}

output "log_analytics_workspace_name" {
  description = "Log Analytics Workspace name"
  value       = module.aks.log_analytics_workspace_name
}

output "storage_account_id" {
  description = "Storage account for diagnostic logs"
  value       = azurerm_storage_account.diagnostic_logs.id
  sensitive   = true
}

# ============================================================================
# Action Group Outputs
# ============================================================================

output "action_group_id" {
  description = "ID of Azure Monitor Action Group for alerts"
  value       = azurerm_monitor_action_group.ants_alerts.id
}

output "action_group_name" {
  description = "Name of Azure Monitor Action Group"
  value       = azurerm_monitor_action_group.ants_alerts.name
}

# ============================================================================
# Quick Reference Summary
# ============================================================================

output "deployment_summary" {
  description = "Quick reference for deployed infrastructure"
  value = {
    # Cluster access
    cluster_name = module.aks.cluster_name
    kubectl_context = "aks-${var.environment}"
    configure_kubectl = "az aks get-credentials --resource-group ${var.resource_group_name} --name ${module.aks.cluster_name} --admin"

    # Container registry
    acr_login_server = azurerm_container_registry.ants.login_server
    docker_login = "az acr login --name ${azurerm_container_registry.ants.name}"

    # Database access
    postgres_fqdn = module.postgresql.server_fqdn
    postgres_database = module.postgresql.database_name
    postgres_user = var.postgres_admin_username

    # Secrets management
    key_vault = module.security.key_vault_name
    key_vault_uri = module.security.key_vault_url

    # Helm deployment
    helm_deploy = "helm install capital-markets ./infra/helm/capital-markets -f ./infra/helm/values-lab.yaml"
    helm_verify = "kubectl get pods"
    helm_logs = "kubectl logs -f deployment/trading-agent"

    # Monitoring
    log_analytics_workspace = module.aks.log_analytics_workspace_name
    action_group = azurerm_monitor_action_group.ants_alerts.name

    # Storage
    anf_account = module.anf.account_name

    # Cost management
    estimated_monthly_cost = "~$1,000 (varies by region and usage)"
    cost_optimization_tips = [
      "Delete unused resources daily",
      "Use low-cost SKUs (D4s_v3 instead of D8s_v5)",
      "Disable monitoring/logging if not needed",
      "Scale down or pause when not in use"
    ]
  }
}

# ============================================================================
# Connection String Outputs (for application configuration)
# ============================================================================

output "connection_strings" {
  description = "Connection strings for application deployment"
  value = {
    postgresql = "postgresql://${var.postgres_admin_username}@${module.postgresql.server_fqdn}:5432/${module.postgresql.database_name}?sslmode=require"
    key_vault_url = module.security.key_vault_url
    acr_registry = azurerm_container_registry.ants.login_server
  }
  sensitive = true
}

# ============================================================================
# Troubleshooting Outputs
# ============================================================================

output "troubleshooting_commands" {
  description = "Useful kubectl commands for troubleshooting"
  value = {
    get_pods = "kubectl get pods -A"
    get_nodes = "kubectl get nodes"
    describe_node = "kubectl describe node <node-name>"
    get_events = "kubectl get events -A --sort-by='.lastTimestamp'"
    view_logs = "kubectl logs -f <pod-name>"
    exec_container = "kubectl exec -it <pod-name> -- /bin/bash"
    port_forward = "kubectl port-forward <pod-name> <local-port>:<container-port>"
    check_pvc = "kubectl get pvc"
    describe_pvc = "kubectl describe pvc <pvc-name>"
    anf_mount_status = "kubectl exec -it <pod-name> -- df -h /mnt/anf"
  }
}
