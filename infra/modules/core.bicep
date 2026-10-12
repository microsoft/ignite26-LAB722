@description('Azure region for all core resources.')
param location string

@description('Deterministic LAB722 resource name prefix.')
param baseName string

@description('Resource tags.')
param tags object

var registryName = replace('${baseName}acr', '-', '')

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs'
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${baseName}-appi'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    DisableLocalAuth: true
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource sandboxIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-sandbox-mi'
  location: location
  tags: tags
}

output containerRegistryName string = containerRegistry.name
output containerRegistryId string = containerRegistry.id
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output logAnalyticsWorkspaceId string = logAnalytics.id
output sandboxIdentityId string = sandboxIdentity.id
output sandboxIdentityPrincipalId string = sandboxIdentity.properties.principalId
