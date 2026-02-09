###############################################################################
# Log Analytics Workspace
###############################################################################

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days

  tags = var.tags
}

###############################################################################
# Log Analytics Solution — Container Insights
###############################################################################

resource "azurerm_log_analytics_solution" "containers" {
  solution_name         = "ContainerInsights"
  workspace_resource_id = azurerm_log_analytics_workspace.main.id
  workspace_name        = azurerm_log_analytics_workspace.main.name
  location              = var.location
  resource_group_name   = var.resource_group_name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }

  tags = var.tags
}

###############################################################################
# Application Insights
###############################################################################

resource "azurerm_application_insights" "main" {
  name                = "ai-agent-mesh-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = var.tags
}

###############################################################################
# Azure Monitor Action Group
###############################################################################

resource "azurerm_monitor_action_group" "critical" {
  name                = "ag-agent-mesh-critical-${var.environment}"
  resource_group_name = var.resource_group_name
  short_name          = "mesh-crit"

  tags = var.tags
}

###############################################################################
# Metric Alert — High CPU on AKS nodes
###############################################################################

resource "azurerm_monitor_metric_alert" "high_cpu" {
  name                = "alert-high-cpu-${var.environment}"
  resource_group_name = var.resource_group_name
  scopes              = [azurerm_log_analytics_workspace.main.id]
  description         = "Alert when average CPU exceeds 85%."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.OperationalInsights/workspaces"
    metric_name      = "Average_% Processor Time"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = var.tags
}
