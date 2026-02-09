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

variable "log_analytics_retention_days" {
  description = "Data retention in days for Log Analytics."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
