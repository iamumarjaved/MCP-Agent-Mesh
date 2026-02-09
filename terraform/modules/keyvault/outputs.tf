output "vault_uri" {
  description = "Key Vault URI."
  value       = azurerm_key_vault.main.vault_uri
}

output "vault_id" {
  description = "Resource ID of the Key Vault."
  value       = azurerm_key_vault.main.id
}

output "vault_name" {
  description = "Name of the Key Vault."
  value       = azurerm_key_vault.main.name
}
