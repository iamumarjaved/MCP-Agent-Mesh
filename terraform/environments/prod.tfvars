environment        = "prod"
location           = "eastus2"
resource_group_name = "rg-agent-mesh"

# AKS
aks_node_count      = 3
aks_vm_size         = "Standard_D4s_v5"
aks_user_node_count = 5
aks_user_vm_size    = "Standard_D8s_v5"
aks_kubernetes_version = "1.28"

# Cosmos DB
cosmos_db_throughput = 0 # serverless

# Redis
redis_sku      = "Premium"
redis_capacity = 1
redis_family   = "P"

# Key Vault
keyvault_sku = "premium"

# Monitoring
log_analytics_retention_days = 90

# Networking
vnet_address_space      = ["10.0.0.0/16"]
aks_subnet_prefix       = "10.0.0.0/20"
services_subnet_prefix  = "10.0.16.0/24"
endpoints_subnet_prefix = "10.0.17.0/24"

# Tags
tags = {
  project     = "agent-mesh"
  managed     = "terraform"
  cost-center = "engineering"
  compliance  = "soc2"
}
