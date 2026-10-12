@description('Azure region for the Foundry resources.')
param location string

@description('Deterministic LAB722 resource name prefix.')
param baseName string

@description('Resource tags.')
param tags object

@description('Foundry model name.')
param modelName string

@description('Foundry model version.')
param modelVersion string

@description('Foundry model provider format.')
param modelFormat string

@description('Foundry model deployment SKU.')
param modelSkuName string

@description('Foundry model deployment capacity.')
param modelCapacity int

@description('Object ID granted project-scoped Foundry data-plane access. Empty skips the role assignment.')
param labUserPrincipalId string

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('Microsoft Entra principal type for the Foundry role assignment.')
param labUserPrincipalType string

@description('Existing project-scoped Foundry User assignment name, if present. Empty generates a deterministic name.')
param foundryUserRoleAssignmentName string = ''

var foundryAccountName = '${baseName}-ai'
var foundryProjectName = 'caldova'
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }

  properties: {}
}

resource foundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(labUserPrincipalId)) {
  name: empty(foundryUserRoleAssignmentName)
    ? guid(foundryProject.id, labUserPrincipalId, foundryUserRoleId)
    : foundryUserRoleAssignmentName
  scope: foundryProject
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalId: labUserPrincipalId
    principalType: labUserPrincipalType
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundryAccount
  name: modelName
  dependsOn: [
    foundryProject
  ]
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: modelFormat
      name: modelName
      version: modelVersion
    }
  }
}

output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output modelDeploymentName string = modelDeployment.name
