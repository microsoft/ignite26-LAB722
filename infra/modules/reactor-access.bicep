param location string
param tags object
param frontendName string
param executionName string
param foundryAccountName string
param foundryProjectName string
param sandboxGroupName string
param registryName string = 'acateam'
param anonymousImagePull bool = true
param enableAgentSwarm bool = false
@description('False reuses harness-created assignments without attempting authorization writes.')
param createRoleAssignments bool = true

var foundryUserRole = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var sandboxOwnerRole = 'c24cf47c-5077-412d-a19c-45202126392c'
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: registryName }
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = { name: foundryAccountName }
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: account
  name: foundryProjectName
}
resource sandboxGroup 'Microsoft.App/sandboxGroups@2026-02-01-preview' existing = { name: sandboxGroupName }
resource frontendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${frontendName}-mi'
  location: location
  tags: tags
}
resource executionIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${executionName}-mi'
  location: location
  tags: tags
}
resource pullRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for identityId in [frontendIdentity.id, executionIdentity.id]: if (createRoleAssignments && !anonymousImagePull) {
    name: guid(registry.id, identityId, acrPullRole)
    scope: registry
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
      principalId: identityId == frontendIdentity.id ? frontendIdentity.properties.principalId : executionIdentity.properties.principalId
      principalType: 'ServicePrincipal'
    }
  }
]
resource frontendFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments) {
  name: guid(project.id, frontendIdentity.id, foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: frontendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource executionSandboxOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments) {
  name: guid(sandboxGroup.id, executionIdentity.id, sandboxOwnerRole)
  scope: sandboxGroup
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sandboxOwnerRole)
    principalId: executionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource executionModelUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments && enableAgentSwarm) {
  name: guid(account.id, executionIdentity.id, foundryUserRole)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: executionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource projectToolboxUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments) {
  name: guid(project.id, 'runtime-toolbox', foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output frontendIdentityId string = frontendIdentity.id
output frontendObjectId string = frontendIdentity.properties.principalId
output frontendClientId string = frontendIdentity.properties.clientId
output executionIdentityId string = executionIdentity.id
output executionObjectId string = executionIdentity.properties.principalId
output executionClientId string = executionIdentity.properties.clientId
output projectObjectId string = project.identity.principalId
