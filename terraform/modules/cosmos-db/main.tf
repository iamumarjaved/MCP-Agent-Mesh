###############################################################################
# Cosmos DB Account (Serverless)
###############################################################################

resource "azurerm_cosmosdb_account" "main" {
  name                = "cosmos-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level       = "Session"
    max_interval_in_seconds = 5
    max_staleness_prefix    = 100
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  is_virtual_network_filter_enabled = true

  virtual_network_rule {
    id = var.subnet_id
  }

  tags = var.tags
}

###############################################################################
# Database
###############################################################################

resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "agent-mesh-db"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
}

###############################################################################
# Containers
###############################################################################

resource "azurerm_cosmosdb_sql_container" "tasks" {
  name                = "tasks"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_path  = "/taskId"

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }

    excluded_path {
      path = "/\"_etag\"/?"
    }
  }

  default_ttl = -1
}

resource "azurerm_cosmosdb_sql_container" "audit_log" {
  name                = "audit_log"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_path  = "/agentId"

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }

    excluded_path {
      path = "/\"_etag\"/?"
    }
  }

  default_ttl = 2592000 # 30 days
}
