targetScope = 'resourceGroup'

@description('The existing AI Foundry account name in this resource group')
param foundryName string
@description('Whether to scope role assignments to a project instead of the account')
param useProject bool = false
@description('The existing project name under the AI Foundry account (if useProject=true)')
param projectName string = ''
@description('Principal id (objectId) of the identity to assign roles to')
param principalId string
@description('The user-assigned identity name (used for deterministic GUID generation)')
param uaiName string
@description('Role definition resource id for Azure AI Developer')
param aiDeveloperRoleDefinitionId string
@description('Role definition resource id for Cognitive Services User')
param cognitiveUserRoleDefinitionId string

// Reference the existing Foundry account in this resource group
resource existingFoundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryName
}

// Optionally reference an existing project under the account
resource existingProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = if (useProject) {
  parent: existingFoundry
  name: projectName
}

// Assign roles on the account (when not scoping to a project)
resource roleAssignAIDeveloper_account 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = if (!useProject) {
  name: guid(existingFoundry.id, principalId, 'ai-dev-role')
  scope: existingFoundry
  properties: {
    roleDefinitionId: aiDeveloperRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource roleAssignCognitiveUser_account 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = if (!useProject) {
  name: guid(existingFoundry.id, principalId, 'cog-user-role')
  scope: existingFoundry
  properties: {
    roleDefinitionId: cognitiveUserRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Assign roles on the project (when scoping to a project)
resource roleAssignAIDeveloper_project 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = if (useProject) {
  name: guid(existingProject.id, principalId, 'ai-dev-role')
  scope: existingProject
  properties: {
    roleDefinitionId: aiDeveloperRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource roleAssignCognitiveUser_project 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = if (useProject) {
  name: guid(existingProject.id, principalId, 'cog-user-role')
  scope: existingProject
  properties: {
    roleDefinitionId: cognitiveUserRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
