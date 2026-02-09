output "endpoint" {
  description = "Azure OpenAI endpoint URL."
  value       = azurerm_cognitive_account.openai.endpoint
}

output "primary_access_key" {
  description = "Primary access key for the OpenAI account."
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}

output "account_id" {
  description = "Resource ID of the Cognitive Services account."
  value       = azurerm_cognitive_account.openai.id
}

output "deployment_names" {
  description = "Names of all deployed models."
  value       = [for d in azurerm_cognitive_deployment.models : d.name]
}
