targetScope = 'resourceGroup'

param location string = 'westus3'
@minLength(2)
@maxLength(32)
param environmentName string
param operatorObjectId string
param projectName string = 'reactor'
param modelCapacity int = 40

var baseName = 'lab722-${uniqueString(subscription().id, resourceGroup().id, environmentName)}'
var tags = {
  lab: 'LAB722'
  purpose: 'reactor-local'
  'azd-env-name': environmentName
}

module foundry '../../infra/modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    baseName: baseName
    tags: tags
    projectName: projectName
    modelName: 'gpt-5.2'
    modelVersion: '2025-12-11'
    modelFormat: 'OpenAI'
    modelSkuName: 'GlobalStandard'
    modelCapacity: modelCapacity
    labUserPrincipalId: operatorObjectId
    labUserPrincipalType: 'User'
  }
}
module express '../../infra/modules/express.bicep' = {
  name: 'express'
  params: { location: location, baseName: baseName, tags: tags }
}
module sandboxes '../../infra/modules/sandboxes.bicep' = {
  name: 'sandboxes'
  params: {
    location: location
    baseName: baseName
    tags: tags
    sandboxIdentityId: ''
    enableGroupIdentity: false
    labUserPrincipalId: operatorObjectId
    labUserPrincipalType: 'User'
    maxSandboxCount: 8
  }
}

output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_LOCATION string = location
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundry.outputs.foundryProjectName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.foundryProjectEndpoint
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundry.outputs.modelDeploymentName
output EXPRESS_ENVIRONMENT_NAME string = express.outputs.expressEnvironmentName
output SANDBOX_GROUP_NAME string = sandboxes.outputs.sandboxGroupName
