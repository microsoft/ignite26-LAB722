targetScope = 'resourceGroup'

@description('Azure region used for LAB722 resources.')
param location string = 'westus3'

@description('Short environment name used for tags and deterministic naming. azd supplies its explicit name; a harness can omit it.')
@minLength(2)
@maxLength(32)
param environmentName string = 'caldova-${uniqueString(resourceGroup().id)}'

@description('Object ID granted Sandbox and project-scoped Foundry data-plane access. Leave empty until attendee identity integration is enabled.')
param labUserPrincipalId string = ''

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('Microsoft Entra principal type for the Sandbox and Foundry data-plane role assignments.')
param labUserPrincipalType string = 'User'

@description('Existing project-scoped Foundry User assignment name. Empty generates a deterministic name.')
param foundryUserRoleAssignmentName string = ''

@description('Foundry model name.')
param modelName string = 'gpt-5.2'

@description('Foundry model version.')
param modelVersion string = '2025-12-11'

@description('Foundry model provider format.')
param modelFormat string = 'OpenAI'

@description('Foundry model deployment SKU.')
param modelSkuName string = 'GlobalStandard'

@description('Foundry model deployment capacity.')
@minValue(1)
param modelCapacity int = 40

@description('Sandbox group capacity; increase only for retained development evidence plus new worker clones.')
@minValue(4)
@maxValue(16)
param sandboxMaxCount int = 8

@description('Opt in to runtime proof or analysis resources. Default preserves the published learner deployment.')
param enableRuntimeProof bool = false

@allowed(['proof', 'analysis'])
param runtimeMode string = 'proof'

param runtimeProofImage string = ''
param runtimeSandboxId string = ''
@secure()
param runtimeProofKey string = ''
param runtimeAppName string = ''
param runtimeSnapshotId string = ''
param runtimeIdentityName string = 'lab722-runtime-proof-mi'
param runtimeRoleAssignmentNames object = {}

var suffix = uniqueString(subscription().id, resourceGroup().id, environmentName)
var baseName = 'lab722-${suffix}'
var tags = {
  'azd-env-name': environmentName
  lab: 'LAB722'
  scenario: 'caldova-research-preview-factory'
}

module core './modules/core.bicep' = {
  name: 'core'
  params: {
    location: location
    baseName: baseName
    tags: tags
  }
}

module foundry './modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    baseName: baseName
    tags: tags
    modelName: modelName
    modelVersion: modelVersion
    modelFormat: modelFormat
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
    labUserPrincipalId: labUserPrincipalId
    labUserPrincipalType: labUserPrincipalType
    foundryUserRoleAssignmentName: foundryUserRoleAssignmentName
  }
}

module express './modules/express.bicep' = {
  name: 'express'
  params: {
    location: location
    baseName: baseName
    tags: tags
  }
}

module sandboxes './modules/sandboxes.bicep' = {
  name: 'sandboxes'
  params: {
    enableGroupIdentity: !(enableRuntimeProof && runtimeMode == 'analysis')
    location: location
    baseName: baseName
    tags: tags
    sandboxIdentityId: core.outputs.sandboxIdentityId
    labUserPrincipalId: labUserPrincipalId
    labUserPrincipalType: labUserPrincipalType
    maxSandboxCount: sandboxMaxCount
  }
}

module runtimeProof './modules/runtime-proof.bicep' = if (enableRuntimeProof) {
  name: 'runtime-proof'
  params: {
    runtimeMode: runtimeMode
    location: location
    tags: union(tags, { purpose: 'runtime-stage1' })
    registryName: core.outputs.containerRegistryName
    expressEnvironmentName: express.outputs.expressEnvironmentName
    foundryAccountName: foundry.outputs.foundryAccountName
    foundryProjectName: foundry.outputs.foundryProjectName
    sandboxGroupName: sandboxes.outputs.sandboxGroupName
    image: runtimeProofImage
    sandboxId: runtimeSandboxId
    snapshotId: runtimeSnapshotId
    proofKey: runtimeProofKey
    appName: empty(runtimeAppName) ? (runtimeMode == 'analysis' ? 'lab722-runtime-analysis' : 'lab722-runtime-stage1') : runtimeAppName
    modelDeployment: foundry.outputs.modelDeploymentName
    identityName: runtimeIdentityName
    roleAssignmentNames: runtimeRoleAssignmentNames
  }
}

output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_LOCATION string = location
output AZURE_ENV_NAME string = environmentName
output AZURE_CONTAINER_REGISTRY_NAME string = core.outputs.containerRegistryName
output APPLICATION_INSIGHTS_CONNECTION_STRING string = core.outputs.applicationInsightsConnectionString
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundry.outputs.foundryProjectName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.foundryProjectEndpoint
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundry.outputs.modelDeploymentName
output EXPRESS_ENVIRONMENT_NAME string = express.outputs.expressEnvironmentName
output SANDBOX_GROUP_NAME string = sandboxes.outputs.sandboxGroupName
output SANDBOX_REGION string = location
output RUNTIME_APP_URL string = enableRuntimeProof ? runtimeProof!.outputs.RUNTIME_APP_URL : ''
output RUNTIME_TOOLBOX_ENDPOINT string = enableRuntimeProof ? runtimeProof!.outputs.RUNTIME_TOOLBOX_ENDPOINT : ''
