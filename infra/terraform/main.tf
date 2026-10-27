terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  # Remote state in a storage account the learner creates once (see lab step 6.T1).
  backend "azurerm" {
    use_azuread_auth = true # Entra ID auth to the state blob, no storage keys
    use_oidc         = true # workload identity federation from the pipeline
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  use_oidc        = true
}

variable "subscription_id" { type = string }
variable "resource_group" { type = string }
variable "learner_id" { type = string }
variable "location" {
  type    = string
  default = "eastus"
}

locals {
  prefix = "orders-${var.learner_id}"
  tags   = { course = "cgi-azure-devops", owner = "traininguser${var.learner_id}", tool = "terraform" }
}

data "azurerm_client_config" "current" {}

resource "azurerm_service_plan" "plan" {
  name                = "asp-${local.prefix}-tf"
  resource_group_name = var.resource_group
  location            = var.location
  os_type             = "Linux"
  sku_name            = "P0v3"
  tags                = local.tags
}

resource "azurerm_linux_web_app" "dev" {
  name                = "app-${local.prefix}-tf-dev"
  resource_group_name = var.resource_group
  location            = var.location
  service_plan_id     = azurerm_service_plan.plan.id
  https_only          = true
  tags                = merge(local.tags, { env = "dev" })

  identity { type = "SystemAssigned" }

  site_config {
    application_stack { python_version = "3.12" }
    app_command_line                  = "gunicorn --bind=0.0.0.0 --timeout 600 app:app"
    health_check_path                 = "/health"
    health_check_eviction_time_in_min = 5
    ftps_state                        = "Disabled"
  }

  app_settings = {
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    APP_ENV                        = "dev"
  }
}

resource "azurerm_key_vault" "kv" {
  name                       = "kv-${local.prefix}-tf"
  resource_group_name        = var.resource_group
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  soft_delete_retention_days = 7
  tags                       = local.tags
}

output "dev_url" { value = "https://${azurerm_linux_web_app.dev.default_hostname}" }
output "key_vault_name" { value = azurerm_key_vault.kv.name }
