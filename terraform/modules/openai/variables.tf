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

variable "models" {
  description = "List of model deployments."
  type = list(object({
    name     = string
    model    = string
    version  = string
    capacity = number
  }))
}

variable "subnet_id" {
  description = "Subnet ID for network ACL rules."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
