output "vnet_id" {
  description = "Resource ID of the virtual network."
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Name of the virtual network."
  value       = azurerm_virtual_network.main.name
}

output "aks_subnet_id" {
  description = "Resource ID of the AKS subnet."
  value       = azurerm_subnet.aks.id
}

output "services_subnet_id" {
  description = "Resource ID of the services subnet."
  value       = azurerm_subnet.services.id
}

output "endpoints_subnet_id" {
  description = "Resource ID of the endpoints subnet."
  value       = azurerm_subnet.endpoints.id
}
