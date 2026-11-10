@description('Azure region for the Sandbox group.')
param location string

@description('Deterministic LAB722 resource name prefix.')
param baseName string

@description('Resource tags.')
param tags object

@description('User-assigned identity resource ID used by the Sandbox group.')
param sandboxIdentityId string

@description('Keep the legacy group identity by default. Generated-analysis Sandboxes must not inherit it.')
param enableGroupIdentity bool = true

@description('Object ID granted Sandbox data-plane access. Empty skips the role assignment.')
param labUserPrincipalId string

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('Microsoft Entra principal type for the Sandbox role assignment.')
param labUserPrincipalType string

@description('Bounded Sandbox group capacity. The attendee scenario needs a primary and three workers.')
@minValue(4)
@maxValue(16)
param maxSandboxCount int = 8

var sandboxDataOwnerRoleId = 'c24cf47c-5077-412d-a19c-45202126392c'

resource sandboxGroup 'Microsoft.App/sandboxGroups@2026-02-01-preview' = {
  name: '${baseName}-sandboxes'
  location: location
  tags: tags
  identity: enableGroupIdentity ? {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sandboxIdentityId}': {}
    }
  } : { type: 'None' }
  properties: {
    defaultCpu: '2'
    defaultMemory: '4Gi'
    defaultDisk: '20Gi'
    maxSandboxCount: maxSandboxCount
    defaultTimeoutSeconds: 7200
  }
}

resource sandboxDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(labUserPrincipalId)) {
  name: guid(sandboxGroup.id, labUserPrincipalId, sandboxDataOwnerRoleId)
  scope: sandboxGroup
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sandboxDataOwnerRoleId)
    principalId: labUserPrincipalId
    principalType: labUserPrincipalType
  }
}

output sandboxGroupName string = sandboxGroup.name
output sandboxGroupId string = sandboxGroup.id
