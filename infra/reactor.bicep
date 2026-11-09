targetScope = 'resourceGroup'

param location string = resourceGroup().location
param registryName string = 'acateam'
@description('Use the verified public registry without image-pull credentials or registry role assignments. Set false only for an allocation-local private registry.')
param anonymousImagePull bool = true
@description('Reuse pre-granted Skillable assignments; default retains standalone deployment behavior.')
param createRoleAssignments bool = true
param expressEnvironmentName string
param foundryAccountName string
param foundryProjectName string = 'caldova'
param sandboxGroupName string
param snapshotId string
param frontendName string = 'lab722-reactor-frontend'
param executionName string = 'lab722-reactor-execution'
@description('Enable the full Sandbox-agent model relay only with an agent-capable snapshot.')
param enableAgentSwarm bool = false
param modelDeployment string = 'gpt-5.2'
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

var tags = { lab: 'LAB722', purpose: 'reactor' }
var frontendIdentityId = resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '${frontendName}-mi')
var executionIdentityId = resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '${executionName}-mi')

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
module access './modules/reactor-access.bicep' = {
  name: 'reactor-access'
  params: {
    location: location
    tags: tags
    frontendName: frontendName
    executionName: executionName
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    sandboxGroupName: sandboxGroupName
    registryName: registryName
    anonymousImagePull: anonymousImagePull
    enableAgentSwarm: enableAgentSwarm
    createRoleAssignments: createRoleAssignments
  }
}
resource execution 'Microsoft.App/containerApps@2026-03-02-preview' = {
  name: executionName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${executionIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8080, transport: 'auto', allowInsecure: false }
      registries: anonymousImagePull ? [] : [{ server: registry.properties.loginServer, identity: executionIdentityId }]
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
          { name: 'AZURE_CLIENT_ID', value: access.outputs.executionClientId }
          { name: 'AZURE_TENANT_ID', value: tenant().tenantId }
          { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
          { name: 'RESOURCE_GROUP', value: resourceGroup().name }
          { name: 'SANDBOX_GROUP', value: sandboxGroupName }
          { name: 'SANDBOX_REGION', value: location }
          { name: 'SANDBOX_SNAPSHOT_ID', value: snapshotId }
          { name: 'EXECUTION_API_AUDIENCE', value: executionApiAudience }
          { name: 'FRONTEND_OBJECT_ID', value: access.outputs.frontendObjectId }
          { name: 'PROJECT_OBJECT_ID', value: project.identity.principalId }
          { name: 'REACTOR_AGENT_SWARM_ENABLED', value: enableAgentSwarm ? 'true' : 'false' }
          { name: 'REACTOR_MODEL_ENDPOINT', value: 'https://${foundryAccountName}.openai.azure.com/openai/v1/chat/completions' }
          { name: 'MODEL_DEPLOYMENT', value: modelDeployment }
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
    userAssignedIdentities: { '${frontendIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8080, transport: 'auto', allowInsecure: false }
      registries: anonymousImagePull ? [] : [{ server: registry.properties.loginServer, identity: frontendIdentityId }]
    }
    template: {
      containers: [{
        name: 'frontend'
        image: serviceImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'REACTOR_COMPONENT', value: 'frontend' }
          { name: 'FRONTEND_PUBLIC_ORIGIN', value: 'https://${frontendName}.${environment.properties.defaultDomain}' }
          { name: 'AZURE_CLIENT_ID', value: access.outputs.frontendClientId }
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
output frontendObjectId string = access.outputs.frontendObjectId
output executionObjectId string = access.outputs.executionObjectId
output projectObjectId string = project.identity.principalId
output executionIdentityId string = access.outputs.executionIdentityId
