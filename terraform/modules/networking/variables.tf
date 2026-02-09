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

variable "vnet_address_space" {
  description = "Address space for the virtual network."
  type        = list(string)
}

variable "aks_subnet_prefix" {
  description = "CIDR prefix for the AKS subnet."
  type        = string
}

variable "services_subnet_prefix" {
  description = "CIDR prefix for the services subnet."
  type        = string
}

variable "endpoints_subnet_prefix" {
  description = "CIDR prefix for the private endpoints subnet."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
