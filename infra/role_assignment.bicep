@description('Environment name (used as prefix)')
param environmentName string = 'dev'
@description('If true the template will reuse an existing AI Foundry account identified by name and resource group')
param useExistingFoundry bool = true
@description('The name of the existing AI Foundry account to reuse (if useExistingFoundry=true)')
param existingFoundryName string = ''
@description('The resource group that contains the existing AI Foundry account (if useExistingFoundry=true)')
param existingFoundryResourceGroup string = ''
@description('If true the template will reuse an existing project under the AI Foundry account')
param useExistingProject bool = false
@description('The name of the existing AI Foundry project to reuse (if useExistingProject=true)')
param aiProjectName string = ''
@description('The name for the user assigned identity to create')
param uaiName string = '${environmentName}-toolagent-uai'

// Role definition resource IDs provided by the user
var aiDeveloperRoleDefinitionId = '/subscriptions/8cebb108-a4d5-402b-a0c4-f7556126277f/providers/Microsoft.Authorization/roleDefinitions/64702f94-c441-49e6-a78b-ef80e0188fee'
var cognitiveUserRoleDefinitionId = '/subscriptions/8cebb108-a4d5-402b-a0c4-f7556126277f/providers/Microsoft.Authorization/roleDefinitions/a97b65f3-24c7-4388-baec-2e87135dc908'

/*
  This module supports two modes:
  - reuse an existing AI Foundry account (and optionally a project) by passing aiFoundryResourceId and setting useExistingFoundry=true
  - (future) create a new AI Foundry account/project when useExistingFoundry=false (not implemented here)

  It creates a user-assigned identity and assigns the requested roles on either the account (default) or the project (if aiProjectName is provided).
*/

// Create the user-assigned managed identity
resource uai 'Microsoft.ManagedIdentity/userAssignedIdentities@2018-11-30' = {
  name: uaiName
  location: resourceGroup().location
}

// Invoke a module deployed into the Foundry account's resource group to assign roles at the correct scope
module assignRoles 'security/roleAssignmentScopeModule.bicep' = if (useExistingFoundry) {
  name: 'assignRolesToFoundry'
  scope: resourceGroup(existingFoundryResourceGroup)
  params: {
    foundryName: existingFoundryName
    useProject: useExistingProject
    projectName: aiProjectName
    principalId: uai.properties.principalId
    uaiName: uai.name
    aiDeveloperRoleDefinitionId: aiDeveloperRoleDefinitionId
    cognitiveUserRoleDefinitionId: cognitiveUserRoleDefinitionId
  }
}

output uaiResourceId string = uai.id
output uaiPrincipalId string = uai.properties.principalId
output uaiClientId string = uai.properties.clientId
