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

variable "aks_principal_id" {
  description = "Principal ID of the AKS kubelet identity for ACR pull role."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
