// orders-api environments for one learner: one P0v3 Linux plan, dev + staging + prod web apps,
// a 'canary' slot on staging, a Key Vault (RBAC mode) and Application Insights.
// Deployed by the pipeline into an existing resource group (rg-orders-<learnerId>).
targetScope = 'resourceGroup'

@description('Short learner suffix, e.g. 136. Keeps global names unique.')
@minLength(2)
@maxLength(6)
param learnerId string

param location string = resourceGroup().location

@allowed(['P0v3', 'P1v3'])
param planSku string = 'P0v3'

// true only for the first deployment, run by the learner as Owner: lets the web apps read
// Key Vault secrets. The pipeline identity (Contributor) always runs with false.
@description('Grant the web apps Key Vault Secrets User (needs Owner rights)')
param assignRoles bool = false

param tags object = {
  course: 'cgi-azure-devops'
  owner: 'traininguser${learnerId}'
}

var prefix = 'orders-${learnerId}'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'asp-${prefix}'
  location: location
  tags: tags
  kind: 'linux'
  sku: { name: planSku }
  properties: { reserved: true }   // reserved = Linux
}

module dev 'modules/webapp.bicep' = {
  name: 'site-dev'
  params: {
    name: 'app-${prefix}-dev'
    location: location
    planId: plan.id
    envName: 'dev'
    appInsightsConnection: appi.properties.ConnectionString
    tags: tags
    keyVaultName: kv.name
  }
}

module stg 'modules/webapp.bicep' = {
  name: 'site-stg'
  params: {
    name: 'app-${prefix}-stg'
    location: location
    planId: plan.id
    envName: 'staging'
    appInsightsConnection: appi.properties.ConnectionString
    tags: tags
    keyVaultName: kv.name
  }
}

module prod 'modules/webapp.bicep' = {
  name: 'site-prod'
  params: {
    name: 'app-${prefix}-prod'
    location: location
    planId: plan.id
    envName: 'production'
    appInsightsConnection: appi.properties.ConnectionString
    tags: tags
    keyVaultName: kv.name
  }
}

resource stgSite 'Microsoft.Web/sites@2024-04-01' existing = {
  name: 'app-${prefix}-stg'
}

resource canary 'Microsoft.Web/sites/slots@2024-04-01' = {
  parent: stgSite
  name: 'canary'
  location: location
  tags: union(tags, { env: 'staging-canary' })
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'gunicorn --bind=0.0.0.0 --timeout 600 app:app'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      healthCheckPath: '/health'
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appi.properties.ConnectionString }
        { name: 'APP_ENV', value: 'staging-canary' }
        { name: 'PAYMENT_GATEWAY_KEY', value: paymentKeyRef }
      ]
    }
  }
  dependsOn: [stg]
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${prefix}-${take(uniqueString(resourceGroup().id), 4)}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true      // access via Azure RBAC roles, not access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7       // short retention for a training lab
    publicNetworkAccess: 'Enabled'     // Microsoft-hosted agents must reach it
  }
}

var paymentKeyRef = '@Microsoft.KeyVault(VaultName=${kv.name};SecretName=PaymentGatewayKey)'

// APP_ENV and SIMULATE_FAILURE stay with their slot during a swap (slot-sticky);
// APP_VERSION travels with the code.
resource stickySettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: stgSite
  name: 'slotConfigNames'
  properties: {
    appSettingNames: ['APP_ENV', 'SIMULATE_FAILURE']
  }
  dependsOn: [stg]
}

// Least privilege for the apps: read secrets from this one vault, nothing else.
var kvSecretsUser = subscriptionResourceId('Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6')   // Key Vault Secrets User
var appPrincipals = [
  dev.outputs.principalId
  stg.outputs.principalId
  prod.outputs.principalId
  canary.identity.principalId
]

resource kvRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for i in range(0, 4): if (assignRoles) {
  name: guid(kv.id, kvSecretsUser, string(i))
  scope: kv
  properties: {
    roleDefinitionId: kvSecretsUser
    principalId: appPrincipals[i]
    principalType: 'ServicePrincipal'
  }
}]

output devUrl string = dev.outputs.url
output stgUrl string = stg.outputs.url
output prodUrl string = prod.outputs.url
output canaryUrl string = 'https://${canary.properties.defaultHostName}'
output keyVaultName string = kv.name
output devPrincipalId string = dev.outputs.principalId
output stgPrincipalId string = stg.outputs.principalId
output prodPrincipalId string = prod.outputs.principalId
output canaryPrincipalId string = canary.identity.principalId
