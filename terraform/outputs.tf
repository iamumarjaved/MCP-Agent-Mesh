###############################################################################
# AKS
###############################################################################

output "aks_cluster_name" {
  description = "Name of the AKS cluster."
  value       = module.aks.cluster_name
}

output "aks_kubeconfig" {
  description = "Kube config for the AKS cluster."
  value       = module.aks.kube_config_raw
  sensitive   = true
}

###############################################################################
# Cosmos DB
###############################################################################

output "cosmos_endpoint" {
  description = "Cosmos DB account endpoint."
  value       = module.cosmos_db.endpoint
}

###############################################################################
# Redis
###############################################################################

output "redis_hostname" {
  description = "Redis Cache hostname."
  value       = module.redis.hostname
}

###############################################################################
# Storage / ACR
###############################################################################

output "acr_login_server" {
  description = "Azure Container Registry login server."
  value       = module.storage.acr_login_server
}

###############################################################################
# Key Vault
###############################################################################

output "keyvault_uri" {
  description = "Key Vault URI."
  value       = module.keyvault.vault_uri
}

###############################################################################
# Azure OpenAI
###############################################################################

output "openai_endpoint" {
  description = "Azure OpenAI endpoint."
  value       = module.openai.endpoint
}

###############################################################################
# Monitoring
###############################################################################

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID."
  value       = module.monitoring.log_analytics_workspace_id
}
