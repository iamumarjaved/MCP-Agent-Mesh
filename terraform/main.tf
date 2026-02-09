###############################################################################
# Resource Group
###############################################################################

resource "azurerm_resource_group" "main" {
  name     = "${var.resource_group_name}-${var.environment}"
  location = var.location
  tags     = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Networking
###############################################################################

module "networking" {
  source = "./modules/networking"

  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  environment            = var.environment
  vnet_address_space     = var.vnet_address_space
  aks_subnet_prefix      = var.aks_subnet_prefix
  services_subnet_prefix = var.services_subnet_prefix
  endpoints_subnet_prefix = var.endpoints_subnet_prefix
  tags                   = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Monitoring (created early — referenced by other modules)
###############################################################################

module "monitoring" {
  source = "./modules/monitoring"

  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  environment                = var.environment
  log_analytics_retention_days = var.log_analytics_retention_days
  tags                       = merge(var.tags, { environment = var.environment })
}

###############################################################################
# AKS
###############################################################################

module "aks" {
  source = "./modules/aks"

  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  environment            = var.environment
  kubernetes_version     = var.aks_kubernetes_version
  system_node_count      = var.aks_node_count
  system_vm_size         = var.aks_vm_size
  user_node_count        = var.aks_user_node_count
  user_vm_size           = var.aks_user_vm_size
  vnet_subnet_id         = module.networking.aks_subnet_id
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  tags                   = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Cosmos DB
###############################################################################

module "cosmos_db" {
  source = "./modules/cosmos-db"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
  throughput          = var.cosmos_db_throughput
  subnet_id           = module.networking.endpoints_subnet_id
  tags                = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Redis
###############################################################################

module "redis" {
  source = "./modules/redis"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
  sku_name            = var.redis_sku
  capacity            = var.redis_capacity
  family              = var.redis_family
  subnet_id           = module.networking.services_subnet_id
  tags                = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Azure OpenAI
###############################################################################

module "openai" {
  source = "./modules/openai"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
  models              = var.openai_models
  subnet_id           = module.networking.endpoints_subnet_id
  tags                = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Storage + ACR
###############################################################################

module "storage" {
  source = "./modules/storage"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
  aks_principal_id    = module.aks.kubelet_identity_object_id
  tags                = merge(var.tags, { environment = var.environment })
}

###############################################################################
# Key Vault
###############################################################################

module "keyvault" {
  source = "./modules/keyvault"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
  sku_name            = var.keyvault_sku
  aks_principal_id    = module.aks.kubelet_identity_object_id
  subnet_id           = module.networking.endpoints_subnet_id
  tags                = merge(var.tags, { environment = var.environment })
}
