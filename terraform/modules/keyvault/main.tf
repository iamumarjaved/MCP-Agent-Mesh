###############################################################################
# Data Source — current Azure client
###############################################################################

data "azurerm_client_config" "current" {}

###############################################################################
# Key Vault
###############################################################################

resource "azurerm_key_vault" "main" {
  name                        = "kv-agent-mesh-${var.environment}"
  resource_group_name         = var.resource_group_name
  location                    = var.location
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = var.sku_name
  soft_delete_retention_days  = 30
  purge_protection_enabled    = true
  enable_rbac_authorization   = false
  enabled_for_disk_encryption = false

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"

    virtual_network_rules {
      subnet_id = var.subnet_id
    }
  }

  tags = var.tags
}

###############################################################################
# Access Policy — Terraform service principal (admin)
###############################################################################

resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get",
    "List",
    "Set",
    "Delete",
    "Purge",
    "Recover",
  ]

  key_permissions = [
    "Get",
    "List",
    "Create",
    "Delete",
    "Purge",
    "Recover",
  ]

  certificate_permissions = [
    "Get",
    "List",
    "Create",
    "Delete",
    "Purge",
    "Recover",
  ]
}

###############################################################################
# Access Policy — AKS managed identity (reader)
###############################################################################

resource "azurerm_key_vault_access_policy" "aks" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = var.aks_principal_id

  secret_permissions = [
    "Get",
    "List",
  ]

  key_permissions = [
    "Get",
    "List",
  ]

  certificate_permissions = [
    "Get",
    "List",
  ]
}
