@description('Azure region for the Express environment.')
param location string

@description('Deterministic LAB722 resource name prefix.')
param baseName string

@description('Resource tags.')
param tags object

resource expressEnvironment 'Microsoft.App/managedEnvironments@2026-03-02-preview' = {
  name: '${baseName}-express'
  location: location
  tags: tags
  properties: {
    environmentMode: 'Express'
  }
}

output expressEnvironmentName string = expressEnvironment.name
output expressEnvironmentId string = expressEnvironment.id
