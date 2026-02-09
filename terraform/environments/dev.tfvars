environment        = "dev"
location           = "eastus2"
resource_group_name = "rg-agent-mesh"

# AKS
aks_node_count      = 2
aks_vm_size         = "Standard_D2s_v5"
aks_user_node_count = 2
aks_user_vm_size    = "Standard_D4s_v5"
aks_kubernetes_version = "1.28"

# Cosmos DB
cosmos_db_throughput = 0 # serverless

# Redis
redis_sku      = "Standard"
redis_capacity = 1
redis_family   = "C"

# Key Vault
keyvault_sku = "standard"

# Monitoring
log_analytics_retention_days = 30

# Tags
tags = {
  project     = "agent-mesh"
  managed     = "terraform"
  cost-center = "engineering"
}
