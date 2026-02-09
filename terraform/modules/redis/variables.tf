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

variable "sku_name" {
  description = "Redis Cache SKU: Basic, Standard, or Premium."
  type        = string
}

variable "capacity" {
  description = "Redis cache capacity."
  type        = number
}

variable "family" {
  description = "Redis cache family (C or P)."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the Redis cache (used for Premium SKU)."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
