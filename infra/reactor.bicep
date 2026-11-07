targetScope = 'resourceGroup'

param location string = resourceGroup().location
param registryName string = 'acateam'
@description('Use the verified public registry without image-pull credentials or registry role assignments. Set false only for an allocation-local private registry.')
param anonymousImagePull bool = true
param expressEnvironmentName string
param foundryAccountName string
param foundryProjectName string = 'caldova'
param sandboxGroupName string
param snapshotId string
@minLength(80)
param serviceImage string
@description('Dedicated audience from a facilitator-supplied existing service API registration. This template never creates tenant resources.')
@minLength(8)
param executionApiAudience string
@description('Exact Responses protocol URL for the learner-created hosted agent. Leave empty during preparation; submissions remain unavailable until connected.')
param hostedResponsesEndpoint string = ''
@secure()
@minLength(12)
@maxLength(1024)
param alicePassword string
@secure()
@minLength(12)
@maxLength(1024)
param bobPassword string

var frontendName = 'lab722-reactor-frontend'
var executionName = 'lab722-reactor-execution'
var foundryUserRole = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var sandboxOwnerRole = 'c24cf47c-5077-412d-a19c-45202126392c'
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var tags = { lab: 'LAB722', purpose: 'reactor' }

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource environment 'Microsoft.App/managedEnvironments@2026-03-02-preview' existing = {
  name: expressEnvironmentName
}
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: account
  name: foundryProjectName
}
resource sandboxGroup 'Microsoft.App/sandboxGroups@2026-02-01-preview' existing = {
  name: sandboxGroupName
}
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
resource pullRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for identityId in [frontendIdentity.id, executionIdentity.id]: if (!anonymousImagePull) {
  name: guid(registry.id, identityId, acrPullRole)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
    principalId: identityId == frontendIdentity.id ? frontendIdentity.properties.principalId : executionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}]
resource frontendFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, frontendIdentity.id, foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: frontendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource executionSandboxOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sandboxGroup.id, executionIdentity.id, sandboxOwnerRole)
  scope: sandboxGroup
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sandboxOwnerRole)
    principalId: executionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource projectToolboxUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // Reuse the existing assignment from the adopted runtime instead of duplicating it.
  name: guid(project.id, 'runtime-toolbox', foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
resource execution 'Microsoft.App/containerApps@2026-03-02-preview' = {
  name: executionName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${executionIdentity.id}': {} }
  }
  dependsOn: [pullRoles, executionSandboxOwner]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8080, transport: 'auto', allowInsecure: false }
      registries: anonymousImagePull ? [] : [{ server: registry.properties.loginServer, identity: executionIdentity.id }]
      secrets: [
        { name: 'alice-password', value: alicePassword }
        { name: 'bob-password', value: bobPassword }
      ]
    }
    template: {
      containers: [{
        name: 'execution'
        image: serviceImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'REACTOR_COMPONENT', value: 'execution' }
          { name: 'AZURE_CLIENT_ID', value: executionIdentity.properties.clientId }
          { name: 'AZURE_TENANT_ID', value: tenant().tenantId }
          { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
          { name: 'RESOURCE_GROUP', value: resourceGroup().name }
          { name: 'SANDBOX_GROUP', value: sandboxGroupName }
          { name: 'SANDBOX_REGION', value: location }
          { name: 'SANDBOX_SNAPSHOT_ID', value: snapshotId }
          { name: 'EXECUTION_API_AUDIENCE', value: executionApiAudience }
          { name: 'FRONTEND_OBJECT_ID', value: frontendIdentity.properties.principalId }
          { name: 'PROJECT_OBJECT_ID', value: project.identity.principalId }
          { name: 'REACTOR_ALICE_PASSWORD', secretRef: 'alice-password' }
          { name: 'REACTOR_BOB_PASSWORD', secretRef: 'bob-password' }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}
resource frontend 'Microsoft.App/containerApps@2026-03-02-preview' = {
  name: frontendName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${frontendIdentity.id}': {} }
  }
  dependsOn: [pullRoles, frontendFoundryUser, projectToolboxUser]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8080, transport: 'auto', allowInsecure: false }
      registries: anonymousImagePull ? [] : [{ server: registry.properties.loginServer, identity: frontendIdentity.id }]
    }
    template: {
      containers: [{
        name: 'frontend'
        image: serviceImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'REACTOR_COMPONENT', value: 'frontend' }
          { name: 'FRONTEND_PUBLIC_ORIGIN', value: 'https://${frontendName}.${environment.properties.defaultDomain}' }
          { name: 'AZURE_CLIENT_ID', value: frontendIdentity.properties.clientId }
          { name: 'EXECUTION_API_AUDIENCE', value: executionApiAudience }
          { name: 'EXECUTION_ENDPOINT', value: 'https://${execution.properties.configuration.ingress.fqdn}' }
          { name: 'HOSTED_RESPONSES_ENDPOINT', value: hostedResponsesEndpoint }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

output frontendEndpoint string = 'https://${frontend.properties.configuration.ingress.fqdn}'
output executionEndpoint string = 'https://${execution.properties.configuration.ingress.fqdn}'
output frontendObjectId string = frontendIdentity.properties.principalId
output executionObjectId string = executionIdentity.properties.principalId
output projectObjectId string = project.identity.principalId
output executionIdentityId string = executionIdentity.id
