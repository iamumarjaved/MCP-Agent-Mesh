output "cluster_name" {
  description = "Name of the AKS cluster."
  value       = azurerm_kubernetes_cluster.main.name
}

output "cluster_id" {
  description = "Resource ID of the AKS cluster."
  value       = azurerm_kubernetes_cluster.main.id
}

output "kube_config_raw" {
  description = "Raw kube config for cluster access."
  value       = azurerm_kubernetes_cluster.main.kube_config_raw
  sensitive   = true
}

output "kubelet_identity_object_id" {
  description = "Object ID of the kubelet managed identity."
  value       = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}

output "node_resource_group" {
  description = "Auto-generated node resource group name."
  value       = azurerm_kubernetes_cluster.main.node_resource_group
}

output "cluster_identity_principal_id" {
  description = "Principal ID of the cluster user-assigned identity."
  value       = azurerm_user_assigned_identity.aks.principal_id
}
