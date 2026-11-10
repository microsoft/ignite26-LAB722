targetScope = 'resourceGroup'

param location string
param tags object
param registryName string
param expressEnvironmentName string
param foundryAccountName string
param foundryProjectName string
param sandboxGroupName string

@allowed(['proof', 'analysis'])
param runtimeMode string = 'proof'
param snapshotId string = ''
param modelDeployment string = 'gpt-5.2'

@description('Approved immutable proof image in the supplied registry. Publish/copy it before enabling this module.')
@minLength(80)
param image string

@description('Existing execution Sandbox ID from the verified clean baseline; not a tenant selected by the model.')
@minLength(36)
@maxLength(36)
param sandboxId string

@secure()
@minLength(32)
param proofKey string

param appName string = runtimeMode == 'analysis' ? 'lab722-runtime-analysis' : 'lab722-runtime-stage1'
param identityName string = 'lab722-runtime-proof-mi'

@description('Preserve existing role assignment names on adopted deployments. Empty values generate deterministic names.')
param roleAssignmentNames object = {}

var foundryUserRole = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var sandboxOwnerRole = 'c24cf47c-5077-412d-a19c-45202126392c'
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var projectEndpoint = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
var toolboxName = runtimeMode == 'analysis' ? 'runtime-analysis-toolbox' : 'runtime-stage1-proof'
var backendName = runtimeMode == 'analysis' ? 'runtime-analysis-backend' : 'runtime-proof-backend'
var toolboxConnectionName = runtimeMode == 'analysis' ? 'runtime-analysis-toolbox' : 'runtime-proof-toolbox'
var toolboxEndpoint = '${projectEndpoint}/toolboxes/${toolboxName}/mcp?api-version=v1'

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

resource group 'Microsoft.App/sandboxGroups@2026-02-01-preview' existing = {
  name: sandboxGroupName
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

resource runtimeFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentNames.?runtimeFoundry ?? guid(project.id, runtimeIdentity.id, foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource runtimeSandboxOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentNames.?runtimeSandbox ?? guid(group.id, runtimeIdentity.id, sandboxOwnerRole)
  scope: group
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sandboxOwnerRole)
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource runtimeAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentNames.?runtimeAcr ?? guid(registry.id, runtimeIdentity.id, acrPullRole)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectToolboxUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentNames.?projectToolbox ?? guid(project.id, 'runtime-toolbox', foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource app 'Microsoft.App/containerApps@2026-03-02-preview' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentity.id}': {}
    }
  }
  dependsOn: [
    runtimeAcrPull
    runtimeFoundryUser
    runtimeSandboxOwner
    projectToolboxUser
  ]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: runtimeIdentity.id
        }
      ]
      secrets: [
        {
          name: 'proof-key'
          value: proofKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'PROOF_KEY', secretRef: 'proof-key' }
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
            { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
            { name: 'RESOURCE_GROUP', value: resourceGroup().name }
            { name: 'SANDBOX_GROUP', value: sandboxGroupName }
            { name: 'SANDBOX_ID', value: sandboxId }
            { name: 'SANDBOX_SNAPSHOT_ID', value: snapshotId }
            { name: 'SANDBOX_REGION', value: location }
            { name: 'SANDBOX_GROUP_IDENTITY_DISABLED', value: runtimeMode == 'analysis' ? 'true' : 'false' }
            { name: 'MODEL_DEPLOYMENT', value: modelDeployment }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'TOOLBOX_ENDPOINT', value: toolboxEndpoint }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource backendConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: backendName
  properties: {
    category: 'RemoteTool'
    authType: 'CustomKeys'
    target: 'https://${app.properties.configuration.ingress.fqdn}/mcp'
    credentials: {
      keys: {
        'X-Lab722-Proof-Key': proofKey
      }
    }
    metadata: {
      lab: 'LAB722'
      purpose: runtimeMode
    }
  }
}

resource toolboxConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: toolboxConnectionName
  properties: {
    category: 'RemoteTool'
    // The deployed Foundry API supports these fields; the installed Bicep type catalog predates them.
    #disable-next-line BCP036
    authType: 'ProjectManagedIdentity'
    #disable-next-line BCP037
    audience: 'https://ai.azure.com'
    target: toolboxEndpoint
    metadata: {
      lab: 'LAB722'
      purpose: runtimeMode
    }
  }
}

output RUNTIME_APP_NAME string = app.name
output RUNTIME_APP_URL string = 'https://${app.properties.configuration.ingress.fqdn}'
output RUNTIME_IDENTITY_ID string = runtimeIdentity.id
output RUNTIME_IDENTITY_CLIENT_ID string = runtimeIdentity.properties.clientId
output RUNTIME_TOOLBOX_ENDPOINT string = toolboxEndpoint
