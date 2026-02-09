###############################################################################
# AKS Managed Identity
###############################################################################

resource "azurerm_user_assigned_identity" "aks" {
  name                = "id-aks-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

###############################################################################
# AKS Cluster
###############################################################################

resource "azurerm_kubernetes_cluster" "main" {
  name                = "aks-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  dns_prefix          = "agent-mesh-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  default_node_pool {
    name                = "system"
    node_count          = var.system_node_count
    vm_size             = var.system_vm_size
    vnet_subnet_id      = var.vnet_subnet_id
    os_disk_size_gb     = 128
    type                = "VirtualMachineScaleSets"
    enable_auto_scaling = true
    min_count           = var.system_node_count
    max_count           = var.system_node_count * 2

    node_labels = {
      "nodepool" = "system"
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.aks.id]
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
    service_cidr      = "172.16.0.0/16"
    dns_service_ip    = "172.16.0.10"
  }

  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  azure_active_directory_role_based_access_control {
    managed            = true
    azure_rbac_enabled = true
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [default_node_pool[0].node_count]
  }
}

###############################################################################
# User Node Pool (Workloads)
###############################################################################

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "workload"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = var.user_vm_size
  node_count            = var.user_node_count
  vnet_subnet_id        = var.vnet_subnet_id
  os_disk_size_gb       = 256
  enable_auto_scaling   = true
  min_count             = var.user_node_count
  max_count             = var.user_node_count * 3
  mode                  = "User"

  node_labels = {
    "nodepool" = "workload"
  }

  node_taints = []

  tags = var.tags

  lifecycle {
    ignore_changes = [node_count]
  }
}
