output "endpoint" {
  description = "Cosmos DB account endpoint."
  value       = azurerm_cosmosdb_account.main.endpoint
}

output "primary_key" {
  description = "Primary master key for the Cosmos DB account."
  value       = azurerm_cosmosdb_account.main.primary_key
  sensitive   = true
}

output "connection_strings" {
  description = "Connection strings for the Cosmos DB account."
  value       = azurerm_cosmosdb_account.main.connection_strings
  sensitive   = true
}

output "database_name" {
  description = "Name of the SQL database."
  value       = azurerm_cosmosdb_sql_database.main.name
}

output "account_id" {
  description = "Resource ID of the Cosmos DB account."
  value       = azurerm_cosmosdb_account.main.id
}
