###############################################################################
# Azure OpenAI Cognitive Services Account
###############################################################################

resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-agent-mesh-${var.environment}"
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-agent-mesh-${var.environment}"

  network_acls {
    default_action = "Deny"

    virtual_network_rules {
      subnet_id = var.subnet_id
    }
  }

  tags = var.tags
}

###############################################################################
# Model Deployments
###############################################################################

resource "azurerm_cognitive_deployment" "models" {
  for_each = { for m in var.models : m.name => m }

  name                 = each.value.name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = each.value.model
    version = each.value.version
  }

  scale {
    type     = "Standard"
    capacity = each.value.capacity
  }
}
