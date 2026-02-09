variable "resource_group_name" {
  description = "Name of the resource group."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version."
  type        = string
}

variable "system_node_count" {
  description = "Number of nodes in the system node pool."
  type        = number
}

variable "system_vm_size" {
  description = "VM size for system node pool."
  type        = string
}

variable "user_node_count" {
  description = "Number of nodes in the user node pool."
  type        = number
}

variable "user_vm_size" {
  description = "VM size for user node pool."
  type        = string
}

variable "vnet_subnet_id" {
  description = "Subnet ID for AKS nodes."
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for OMS agent."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
