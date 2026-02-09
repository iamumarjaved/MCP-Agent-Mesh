###############################################################################
# Azure Redis Cache
###############################################################################

resource "azurerm_redis_cache" "main" {
  name                = "redis-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  capacity            = var.capacity
  family              = var.family
  sku_name            = var.sku_name

  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = var.tags
}

###############################################################################
# Firewall Rules — allow Azure services
###############################################################################

resource "azurerm_redis_firewall_rule" "allow_azure" {
  name                = "AllowAzureServices"
  redis_cache_name    = azurerm_redis_cache.main.name
  resource_group_name = var.resource_group_name
  start_ip            = "0.0.0.0"
  end_ip              = "0.0.0.0"
}
