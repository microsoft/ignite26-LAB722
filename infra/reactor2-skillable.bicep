targetScope = 'resourceGroup'

param location string = resourceGroup().location
@minValue(1)
param modelCapacity int = 40

var suffix = uniqueString(subscription().id, resourceGroup().id)
var baseName = 'lab722-${suffix}'
var frontendName = 'r2-front-${suffix}'
var executionName = 'r2-exec-${suffix}'
var tags = { lab: 'LAB722', purpose: 'reactor2-skillable', 'azd-env-name': 'reactor2-${suffix}' }

module core './modules/core.bicep' = {
  name: 'reactor2-core'
  params: { location: location, baseName: baseName, tags: tags }
}
module foundry './modules/foundry.bicep' = {
  name: 'reactor2-foundry'
  params: {
    location: location
    baseName: baseName
    tags: tags
    projectName: 'reactor'
    modelName: 'gpt-5.2'
    modelVersion: '2025-12-11'
    modelFormat: 'OpenAI'
    modelSkuName: 'GlobalStandard'
    modelCapacity: modelCapacity
    labUserPrincipalId: ''
    labUserPrincipalType: 'User'
  }
}
module express './modules/express.bicep' = {
  name: 'reactor2-express'
  params: { location: location, baseName: baseName, tags: tags }
}
module sandboxes './modules/sandboxes.bicep' = {
  name: 'reactor2-sandboxes'
  params: {
    location: location
    baseName: baseName
    tags: tags
    sandboxIdentityId: ''
    enableGroupIdentity: false
    labUserPrincipalId: ''
    labUserPrincipalType: 'User'
    maxSandboxCount: 8
  }
}
module access './modules/reactor-access.bicep' = {
  name: 'reactor2-access'
  params: {
    location: location
    tags: tags
    frontendName: frontendName
    executionName: executionName
    foundryAccountName: foundry.outputs.foundryAccountName
    foundryProjectName: foundry.outputs.foundryProjectName
    sandboxGroupName: sandboxes.outputs.sandboxGroupName
    registryName: core.outputs.containerRegistryName
    anonymousImagePull: true
    enableAgentSwarm: true
    createRoleAssignments: false
  }
}

output REACTOR2_HARNESS_VERSION string = '1'
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_LOCATION string = location
output AZURE_ENV_NAME string = 'reactor2-${suffix}'
output AZURE_CONTAINER_REGISTRY_NAME string = core.outputs.containerRegistryName
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundry.outputs.foundryProjectName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.foundryProjectEndpoint
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundry.outputs.modelDeploymentName
output EXPRESS_ENVIRONMENT_NAME string = express.outputs.expressEnvironmentName
output SANDBOX_GROUP_NAME string = sandboxes.outputs.sandboxGroupName
output REACTOR2_FRONTEND_NAME string = frontendName
output REACTOR2_EXECUTION_NAME string = executionName
output REACTOR2_PROJECT_OBJECT_ID string = access.outputs.projectObjectId
output REACTOR2_FRONTEND_OBJECT_ID string = access.outputs.frontendObjectId
output REACTOR2_EXECUTION_OBJECT_ID string = access.outputs.executionObjectId
output REACTOR2_ARM_ROLE_ASSIGNMENT_COUNT int = 0
output REACTOR2_LCA_ROLE_ASSIGNMENT_COUNT int = 8
