output "hostname" {
  description = "Redis Cache hostname."
  value       = azurerm_redis_cache.main.hostname
}

output "ssl_port" {
  description = "Redis Cache SSL port."
  value       = azurerm_redis_cache.main.ssl_port
}

output "primary_access_key" {
  description = "Primary access key for Redis."
  value       = azurerm_redis_cache.main.primary_access_key
  sensitive   = true
}

output "primary_connection_string" {
  description = "Primary connection string for Redis."
  value       = azurerm_redis_cache.main.primary_connection_string
  sensitive   = true
}

output "id" {
  description = "Resource ID of the Redis Cache."
  value       = azurerm_redis_cache.main.id
}
