###############################################################################
# General
###############################################################################

variable "resource_group_name" {
  description = "Name of the Azure resource group."
  type        = string
  default     = "rg-agent-mesh"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus2"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default = {
    project   = "agent-mesh"
    managed   = "terraform"
  }
}

###############################################################################
# AKS
###############################################################################

variable "aks_node_count" {
  description = "Number of nodes in the default (system) node pool."
  type        = number
  default     = 2
}

variable "aks_vm_size" {
  description = "VM size for AKS system node pool."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "aks_user_node_count" {
  description = "Number of nodes in the user (workload) node pool."
  type        = number
  default     = 2
}

variable "aks_user_vm_size" {
  description = "VM size for AKS user node pool."
  type        = string
  default     = "Standard_D4s_v5"
}

variable "aks_kubernetes_version" {
  description = "Kubernetes version for the AKS cluster."
  type        = string
  default     = "1.28"
}

###############################################################################
# Cosmos DB
###############################################################################

variable "cosmos_db_throughput" {
  description = "Max autoscale throughput (RU/s) for Cosmos DB containers. Set to 0 for serverless."
  type        = number
  default     = 0
}

###############################################################################
# Redis
###############################################################################

variable "redis_sku" {
  description = "Redis Cache SKU: Basic, Standard, or Premium."
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.redis_sku)
    error_message = "Redis SKU must be one of: Basic, Standard, Premium."
  }
}

variable "redis_capacity" {
  description = "Redis cache capacity (family-dependent size)."
  type        = number
  default     = 1
}

variable "redis_family" {
  description = "Redis cache family (C for Basic/Standard, P for Premium)."
  type        = string
  default     = "C"
}

###############################################################################
# Azure OpenAI
###############################################################################

variable "openai_models" {
  description = "List of Azure OpenAI model deployments."
  type = list(object({
    name    = string
    model   = string
    version = string
    capacity = number
  }))
  default = [
    {
      name     = "gpt-4o"
      model    = "gpt-4o"
      version  = "2024-05-13"
      capacity = 30
    },
    {
      name     = "gpt-4o-mini"
      model    = "gpt-4o-mini"
      version  = "2024-07-18"
      capacity = 60
    }
  ]
}

###############################################################################
# Networking
###############################################################################

variable "vnet_address_space" {
  description = "Address space for the virtual network."
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "aks_subnet_prefix" {
  description = "CIDR prefix for AKS subnet."
  type        = string
  default     = "10.0.0.0/20"
}

variable "services_subnet_prefix" {
  description = "CIDR prefix for services subnet."
  type        = string
  default     = "10.0.16.0/24"
}

variable "endpoints_subnet_prefix" {
  description = "CIDR prefix for private endpoints subnet."
  type        = string
  default     = "10.0.17.0/24"
}

###############################################################################
# Key Vault
###############################################################################

variable "keyvault_sku" {
  description = "Key Vault SKU: standard or premium."
  type        = string
  default     = "standard"
}

###############################################################################
# Monitoring
###############################################################################

variable "log_analytics_retention_days" {
  description = "Log Analytics workspace retention in days."
  type        = number
  default     = 30
}
