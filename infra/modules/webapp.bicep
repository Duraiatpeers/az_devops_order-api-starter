// One Linux web app (Python 3.12) on an existing plan. siteConfig is written inline (not built with
// union()) so IaC scanners such as Checkov can read the security settings.
param name string
param location string
param planId string
param envName string
param appInsightsConnection string
param tags object
@description('Key Vault holding PaymentGatewayKey; read at runtime by the app identity')
param keyVaultName string

var paymentKeyRef = '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=PaymentGatewayKey)'

resource site 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: union(tags, { env: envName })
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: planId
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
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnection }
        { name: 'APP_ENV', value: envName }
        { name: 'PAYMENT_GATEWAY_KEY', value: paymentKeyRef }
      ]
    }
  }
}

output name string = site.name
output url string = 'https://${site.properties.defaultHostName}'
output principalId string = site.identity.principalId
