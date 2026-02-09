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

variable "throughput" {
  description = "Max autoscale throughput. Set to 0 for serverless."
  type        = number
  default     = 0
}

variable "subnet_id" {
  description = "Subnet ID for virtual network rules."
  type        = string
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
