param environmentName string = 'dev'
param location string = resourceGroup().location

@description('If reusing an existing Foundry account, set to true')
param useExistingFoundry bool = true
@description('Existing Foundry account name (used when useExistingFoundry=true)')
param existingFoundryName string = 'azure-ai-agents-demo'
@description('Resource group that contains the existing Foundry account')
param existingFoundryResourceGroup string = 'rg-azure-ai-agents'
@description('If scoping roles to an existing project')
param useExistingProject bool = true
@description('Existing Foundry project name')
param aiProjectName string = 'firstProject'

// Azure AI configuration
@description('Azure AI Project Endpoint URL')
param azureAiProjectEndpoint string = ''
@description('Azure OpenAI model name to use')
param azureOpenAiModel string = 'gpt-4o'

// Agent configuration
@description('Deploy tool agent')
param deployToolAgent bool = true
@description('Deploy reimbursement agent')
param deployReimbursementAgent bool = true
@description('Deploy analytics agent')
param deployAnalyticsAgent bool = true

// Shared UAI for all agents
param sharedUaiName string = '${environmentName}-multiagent-uai'

// Common infrastructure
var commonPrefix = '${environmentName}-multiagent'
var appServicePlanName = '${commonPrefix}-plan'
var appInsightsName = '${commonPrefix}-ai'

// Tool Agent resources
var toolAgentPrefix = '${environmentName}-toolagent'
var toolAgentWebAppName = '${toolAgentPrefix}-web'

// Reimbursement Agent resources
var reimbursementAgentPrefix = '${environmentName}-reimbursementagent'
var reimbursementAgentWebAppName = '${reimbursementAgentPrefix}-web'

// Analytics Agent resources
var analyticsAgentPrefix = '${environmentName}-analyticsagent'
var analyticsAgentWebAppName = '${analyticsAgentPrefix}-web'

// Shared UAI resource ID
var sharedUaiResourceId = resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', sharedUaiName)

// Create the shared UAI and role assignments (used by all agents)
module createSharedUAI 'role_assignment.bicep' = {
  name: 'createSharedUAI'
  params: {
    environmentName: environmentName
    useExistingFoundry: useExistingFoundry
    existingFoundryName: existingFoundryName
    existingFoundryResourceGroup: existingFoundryResourceGroup
    useExistingProject: useExistingProject
    aiProjectName: aiProjectName
    uaiName: sharedUaiName
  }
}

resource plan 'Microsoft.Web/serverfarms@2021-02-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    capacity: 1
  }
  properties: {
    reserved: true // Linux
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource webApp 'Microsoft.Web/sites@2021-02-01' = if (deployToolAgent) {
  name: toolAgentWebAppName
  location: location
  kind: 'app,linux'
  tags: {
    'azd-service-name': 'toolAgent'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sharedUaiResourceId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'gunicorn -k uvicorn.workers.UvicornWorker -w 4 "app:app" --bind 0.0.0.0:$PORT'
      healthCheckPath: '/health'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '0'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES'
          value: '3'
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXUNHEALTHYWORKERPERCENT'
          value: '50'
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: azureAiProjectEndpoint
        }
        {
          name: 'model'
          value: azureOpenAiModel
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: createSharedUAI.outputs.uaiClientId
        }
      ]
    }
  }
  dependsOn: [createSharedUAI]
}

resource reimbursementWebApp 'Microsoft.Web/sites@2021-02-01' = if (deployReimbursementAgent) {
  name: reimbursementAgentWebAppName
  location: location
  kind: 'app,linux'
  tags: {
    'azd-service-name': 'reimbursementAgent'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sharedUaiResourceId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.13'
      appCommandLine: 'gunicorn -k uvicorn.workers.UvicornWorker -w 4 "app:app" --bind 0.0.0.0:$PORT'
      healthCheckPath: '/health'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '0'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES'
          value: '3'
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXUNHEALTHYWORKERPERCENT'
          value: '50'
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: azureAiProjectEndpoint
        }
        {
          name: 'model'
          value: azureOpenAiModel
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: createSharedUAI.outputs.uaiClientId
        }
      ]
    }
  }
  dependsOn: [createSharedUAI]
}

resource analyticsWebApp 'Microsoft.Web/sites@2021-02-01' = if (deployAnalyticsAgent) {
  name: analyticsAgentWebAppName
  location: location
  kind: 'app,linux'
  tags: {
    'azd-service-name': 'analyticsAgent'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sharedUaiResourceId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.13'
      appCommandLine: 'gunicorn -k uvicorn.workers.UvicornWorker -w 4 "app:app" --bind 0.0.0.0:$PORT'
      healthCheckPath: '/health'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '0'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES'
          value: '3'
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXUNHEALTHYWORKERPERCENT'
          value: '50'
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: azureAiProjectEndpoint
        }
        {
          name: 'model'
          value: azureOpenAiModel
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: createSharedUAI.outputs.uaiClientId
        }
      ]
    }
  }
  dependsOn: [createSharedUAI]
}

// Tool Agent outputs
output webAppName string = deployToolAgent ? webApp!.name : ''
output webAppDefaultHostName string = deployToolAgent ? webApp!.properties.defaultHostName : ''
output toolAgent_webAppName string = deployToolAgent ? webApp!.name : ''
output toolAgent_webAppDefaultHostName string = deployToolAgent ? webApp!.properties.defaultHostName : ''
output toolAgent_webAppResourceId string = deployToolAgent ? webApp!.id : ''

// Reimbursement Agent outputs
output reimbursementAgent_webAppName string = deployReimbursementAgent ? reimbursementWebApp!.name : ''
output reimbursementAgent_webAppDefaultHostName string = deployReimbursementAgent ? reimbursementWebApp!.properties.defaultHostName : ''
output reimbursementAgent_webAppResourceId string = deployReimbursementAgent ? reimbursementWebApp!.id : ''

// Analytics Agent outputs
output analyticsAgent_webAppName string = deployAnalyticsAgent ? analyticsWebApp!.name : ''
output analyticsAgent_webAppDefaultHostName string = deployAnalyticsAgent ? analyticsWebApp!.properties.defaultHostName : ''
output analyticsAgent_webAppResourceId string = deployAnalyticsAgent ? analyticsWebApp!.id : ''
