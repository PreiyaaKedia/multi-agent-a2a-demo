# Multi-Agent A2A Sample Demo

A comprehensive demonstration of the Agent-to-Agent (A2A) protocol enabling seamless collaboration between AI agents across different frameworks and platforms. This project showcases how agents built with Google ADK, CrewAI, and Azure AI Foundry Agent service can communicate and collaborate through standardized A2A protocol.

## 🏗️ Architecture Overview

![A2A Workflow](images/a2a-image.png)

This demo implements a multi-agent system where specialized agents collaborate to handle complex business workflows:

- **Routing Agent**: Discovers and routes tasks to appropriate agents based on capabilities
- **Invoice Extraction Agent** (tool_agent): Extracts structured data from receipts and invoices using MCP server
- **Reimbursement Agent**: Handles expense reimbursement workflows using Google ADK
- **Analytics Agent**: Creates charts and visualizations using CrewAI
- **MCP Server**: Azure Function App providing document processing capabilities

## 🤖 Agent Components

### 1. Routing Agent
- **Framework**: Azure AI Foundry Agent service with Semantic Kernel
- **Location**: `src/multi_agent/host_agent/routing_agent.py`
- **Purpose**: Orchestrates agent discovery and task routing based on agent cards and capabilities
- **Features**:
  - Dynamic agent discovery via A2A protocol
  - Intelligent task assignment based on agent capabilities
  - Context-aware routing decisions

### 2. Invoice Extraction Agent (Tool Agent)
- **Framework**: Azure AI Foundry Agent service with Semantic Kernel + MCP integration
- **Location**: `src/multi_agent/remote_agents/tool_agent/`
- **Purpose**: Extracts structured information from uploaded receipts and invoices
- **Features**:
  - MCP server integration for document processing
  - Azure Content Understanding for intelligent extraction
  - Structured data output for downstream processing

### 3. Reimbursement Agent
- **Framework**: Google ADK (Agent Development Kit)
- **Location**: `src/multi_agent/remote_agents/reimbursement_agent/`
- **Purpose**: Processes expense reimbursement requests and workflows
- **Features**:
  - Expense form creation and validation
  - Reimbursement workflow management
  - Integration with expense tracking systems

### 4. Analytics Agent
- **Framework**: CrewAI
- **Location**: `src/multi_agent/remote_agents/analytics_agent/`
- **Purpose**: Creates data visualizations and analytical insights
- **Features**:
  - Chart and graph generation using matplotlib
  - Data analysis and visualization
  - PDF report generation

### 5. MCP Server Function App
- **Platform**: Azure Functions
- **Location**: `src/multi_agent/remote_agents/mcp_server_func_app/`
- **Purpose**: Provides Model Context Protocol (MCP) server for document processing
- **Features**:
  - Blob storage integration for file management
  - Azure Content Understanding for document analysis
  - PDF conversion and structured data extraction
  - RESTful API endpoints for agent integration

## 🔧 Technology Stack

### Core Frameworks
- **A2A Protocol**: Agent-to-Agent communication standard
- **Azure AI Foundry**: Agent hosting and management
- **Google ADK**: Agent development and deployment
- **CrewAI**: Multi-agent orchestration framework
- **Semantic Kernel**: AI orchestration and integration
- **Azure Functions**: Serverless compute for MCP server

### AI Services
- **Azure OpenAI**: Large language model provider via LiteLLM
- **Azure Content Understanding**: Document intelligence and extraction
- **LiteLLM**: Universal LLM gateway supporting multiple providers

### Infrastructure
- **Azure App Service**: Agent hosting platform
- **Azure Blob Storage**: Document and file storage
- **Azure Bicep**: Infrastructure as Code
- **Azure Developer CLI (azd)**: Deployment automation

## 🚀 Getting Started

### Prerequisites
- Azure subscription with appropriate permissions
- Python 3.13+
- Node.js 18+
- Azure CLI
- Azure Developer CLI (azd)F

### Environment Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd multi-agent-a2a-sample-demo
```

2. **Install dependencies**:
```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies
npm install
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your Azure and service configurations
```

### Deployment

The project uses Azure Developer CLI (azd) with custom deployment hooks to handle the zip-based deployment process for Azure App Services.

#### Option 1: Deploy All Services with Azure Developer CLI
```bash
# Provision infrastructure and deploy all services
azd up
```

#### Option 2: Deploy Individual Components

1. **Provision Infrastructure** (if not already done):
```bash
azd provision
```

2. **Deploy Individual Agent Services**:
```bash
# Deploy specific agents
azd deploy toolAgent
azd deploy reimbursementAgent  
azd deploy analyticsAgent
```

3. **Deploy MCP Server Function App**:
```bash
cd src/multi_agent/remote_agents/mcp_server_func_app
func azure functionapp publish <your-function-app-name>
```

#### Custom Deployment Process

The deployment process uses PowerShell scripts integrated with azd hooks:

1. **Pre-deployment**: Creates zip packages for each agent using `Compress-Archive`
2. **Deployment**: Uses `az webapp deployment source config-zip` to deploy packages
3. **Post-deployment**: Cleans up temporary files and validates deployments

**Manual Deployment Alternative**:
If you prefer to deploy manually using the traditional approach:

```powershell
# Create zip package for an agent
$agentPath = "src/multi_agent/remote_agents/tool_agent"
$zipPath = "tool_agent_package.zip"
Compress-Archive -Path "$agentPath\*" -DestinationPath $zipPath -Force

# Configure app settings before deployment
az webapp config appsettings set `
  --resource-group <your-resource-group> `
  --name <your-app-service-name> `
  --settings "WEBSITE_RUN_FROM_PACKAGE=0" "SCM_DO_BUILD_DURING_DEPLOYMENT=true"

# Deploy to Azure App Service
az webapp deployment source config-zip `
  --resource-group <your-resource-group> `
  --name <your-app-service-name> `
  --src $zipPath

# Configure startup command after deployment
az webapp config set `
  --resource-group <your-resource-group> `
  --name <your-app-service-name> `
  --startup-file 'uvicorn app:app --host 0.0.0.0 --port $PORT'

# Clean up
Remove-Item $zipPath
```

#### Setting up azd Deploy Integration

To integrate your zip-based deployment with `azd deploy`, create deployment hooks:

1. **Create deployment hook directory**:
```bash
mkdir -p .azure/hooks
```

2. **Create pre-deployment hook** (`.azure/hooks/predeploy.ps1`):
```powershell
# Pre-deployment hook to create zip packages
param($serviceName)

Write-Host "Creating deployment package for $serviceName..."

$projectPaths = @{
    "toolAgent" = "src/multi_agent/remote_agents/tool_agent"
    "reimbursementAgent" = "src/multi_agent/remote_agents/reimbursement_agent"
    "analyticsAgent" = "src/multi_agent/remote_agents/analytics_agent"
}

if ($projectPaths.ContainsKey($serviceName)) {
    $sourcePath = $projectPaths[$serviceName]
    $zipPath = "${serviceName}_package.zip"
    
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    
    Compress-Archive -Path "$sourcePath\*" -DestinationPath $zipPath -Force
    Write-Host "Package created: $zipPath"
}
```

3. **Create deployment hook** (`.azure/hooks/deploy.ps1`):
```powershell
# Custom deployment hook using az webapp
param($serviceName, $resourceGroupName)

Write-Host "Configuring and deploying $serviceName to Azure App Service..."

$zipPath = "${serviceName}_package.zip"

if (Test-Path $zipPath) {
    # Get the app service name from azd environment
    $appServiceName = azd env get-values | Select-String "${serviceName}Name" | ForEach-Object { $_.ToString().Split('=')[1].Trim('"') }
    
    if ($appServiceName) {
        # Pre-deployment: Configure app settings for package deployment
        Write-Host "Configuring app settings for $appServiceName..."
        az webapp config appsettings set `
            --resource-group $resourceGroupName `
            --name $appServiceName `
            --settings "WEBSITE_RUN_FROM_PACKAGE=0" "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
        
        # Deploy the package
        Write-Host "Deploying package to $appServiceName..."
        az webapp deployment source config-zip `
            --resource-group $resourceGroupName `
            --name $appServiceName `
            --src $zipPath
        
        Write-Host "Successfully deployed $serviceName to $appServiceName"
    } else {
        Write-Error "Could not find app service name for $serviceName"
    }
} else {
    Write-Error "Package not found: $zipPath"
}
```

4. **Create post-deployment cleanup** (`.azure/hooks/postdeploy.ps1`):
```powershell
# Post-deployment cleanup and configuration
param($serviceName, $resourceGroupName)

Write-Host "Post-deployment configuration for $serviceName..."

# Configure startup command for specific services
$startupCommands = @{
    "toolAgent" = "uvicorn app:app --host 0.0.0.0 --port `$PORT"
    "reimbursementAgent" = "uvicorn app:app --host 0.0.0.0 --port `$PORT"
    "analyticsAgent" = "uvicorn app:app --host 0.0.0.0 --port `$PORT"
}

if ($startupCommands.ContainsKey($serviceName)) {
    $appServiceName = azd env get-values | Select-String "${serviceName}Name" | ForEach-Object { $_.ToString().Split('=')[1].Trim('"') }
    
    if ($appServiceName) {
        Write-Host "Setting startup command for $appServiceName..."
        az webapp config set `
            --resource-group $resourceGroupName `
            --name $appServiceName `
            --startup-file $startupCommands[$serviceName]
        
        Write-Host "Startup command configured for $serviceName"
    }
}

# Clean up deployment package
$zipPath = "${serviceName}_package.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "Cleaned up package: $zipPath"
}
```

5. **Update azure.yaml** to use deployment hooks:
```yaml
name: a2a-multi-agent
services:
  toolAgent:
    project: ./src/multi_agent/remote_agents/tool_agent
    language: python
    host: appservice
    hooks:
      predeploy:
        shell: pwsh
        run: .azure/hooks/predeploy.ps1 toolAgent
      deploy:
        shell: pwsh  
        run: .azure/hooks/deploy.ps1 toolAgent $AZURE_RESOURCE_GROUP
      postdeploy:
        shell: pwsh
        run: .azure/hooks/postdeploy.ps1 toolAgent $AZURE_RESOURCE_GROUP
  reimbursementAgent:
    project: ./src/multi_agent/remote_agents/reimbursement_agent
    language: python
    host: appservice
    hooks:
      predeploy:
        shell: pwsh
        run: .azure/hooks/predeploy.ps1 reimbursementAgent
      deploy:
        shell: pwsh
        run: .azure/hooks/deploy.ps1 reimbursementAgent $AZURE_RESOURCE_GROUP
      postdeploy:
        shell: pwsh
        run: .azure/hooks/postdeploy.ps1 reimbursementAgent $AZURE_RESOURCE_GROUP
  analyticsAgent:
    project: ./src/multi_agent/remote_agents/analytics_agent
    language: python
    host: appservice
    hooks:
      predeploy:
        shell: pwsh
        run: .azure/hooks/predeploy.ps1 analyticsAgent
      deploy:
        shell: pwsh
        run: .azure/hooks/deploy.ps1 analyticsAgent $AZURE_RESOURCE_GROUP
      postdeploy:
        shell: pwsh
        run: .azure/hooks/postdeploy.ps1 analyticsAgent $AZURE_RESOURCE_GROUP
infra:
  provider: bicep
```

## 🔄 A2A Protocol Implementation

### Agent Discovery
Each agent publishes an agent card at `/.well-known/agent.json` containing:
- Agent capabilities and skills
- Supported input/output modalities
- Communication endpoints
- Protocol version information

### Message Flow
1. **Discovery Phase**: Routing agent discovers available agents via agent cards
2. **Task Assignment**: Based on user query and agent capabilities
3. **Inter-Agent Communication**: Standardized A2A message exchange
4. **Result Aggregation**: Consolidated response from multiple agents

### Protocol Standards
- **JSON-RPC 2.0**: Underlying communication protocol
- **Standardized Payloads**: Consistent message formats across frameworks
- **Agent Cards**: Self-describing agent capabilities
- **Task Lifecycle Management**: Stateful task tracking and updates

## 📋 Usage Examples

### Invoice Processing Workflow
```
User: "Extract information from this receipt and process reimbursement"
├── Routing Agent → Tool Agent (receipt extraction)
├── Tool Agent → MCP Server (document processing)
├── Routing Agent → Reimbursement Agent (expense processing)
└── Combined response with structured data and reimbursement status
```

### Analytics and Reporting
```
User: "Create a chart showing expense trends"
├── Routing Agent → Analytics Agent (visualization)
├── Analytics Agent → Chart generation
└── Response with generated charts and insights
```

## 🏗️ Infrastructure

The project includes Bicep templates for Azure infrastructure deployment:

- **main.bicep**: Core infrastructure resources
- **static-web-app.bicep**: Frontend hosting configuration
- **app/api.bicep**: API and function app resources
- **security/**: RBAC and security configurations

## 🔒 Security

- **Managed Identity**: Azure services use managed identities for authentication
- **RBAC**: Role-based access control for resource permissions
- **Key Vault Integration**: Secure storage for sensitive configuration
- **Network Security**: Proper network isolation and access controls

## 📊 Monitoring and Observability

- **Application Insights**: Telemetry and performance monitoring
- **Azure Monitor**: Infrastructure and service health monitoring
- **Logging**: Comprehensive logging across all components
- **Health Checks**: Service availability and readiness endpoints

## 🚨 Troubleshooting

### Deployment Issues

**azd deploy not working with zip-based deployment:**
- Ensure PowerShell execution policy allows script execution: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Verify Azure CLI is installed and authenticated: `az account show`
- Check that deployment hooks have proper permissions and paths

**Manual deployment fallback:**
```powershell
# If azd deploy fails, use manual deployment
$agents = @("toolAgent", "reimbursementAgent", "analyticsAgent")
foreach ($agent in $agents) {
    $sourcePath = "src/multi_agent/remote_agents/$($agent.ToLower() -replace 'agent', '_agent')"
    $zipPath = "${agent}_package.zip"
    
    Compress-Archive -Path "$sourcePath\*" -DestinationPath $zipPath -Force
    
    # Get resource group and app service name from azd
    $resourceGroup = azd env get-values | Select-String "AZURE_RESOURCE_GROUP" | ForEach-Object { $_.ToString().Split('=')[1].Trim('"') }
    $appServiceName = azd env get-values | Select-String "${agent}Name" | ForEach-Object { $_.ToString().Split('=')[1].Trim('"') }
    
    # Pre-deployment: Configure app settings
    Write-Host "Configuring app settings for $appServiceName..."
    az webapp config appsettings set `
        --resource-group $resourceGroup `
        --name $appServiceName `
        --settings "WEBSITE_RUN_FROM_PACKAGE=0" "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
    
    # Deploy the package
    Write-Host "Deploying $agent..."
    az webapp deployment source config-zip --resource-group $resourceGroup --name $appServiceName --src $zipPath
    
    # Post-deployment: Configure startup command
    Write-Host "Configuring startup command for $appServiceName..."
    az webapp config set `
        --resource-group $resourceGroup `
        --name $appServiceName `
        --startup-file "uvicorn app:app --host 0.0.0.0 --port `$PORT"
    
    Remove-Item $zipPath -Force
    Write-Host "$agent deployment completed successfully"
}
```

**Common Issues:**
- **Permission errors**: Ensure your account has Contributor role on the resource group
- **Package size limits**: Azure App Service has deployment size limits (typically 2GB)
- **Startup failures**: Check Application Insights logs for detailed error information
- **Port binding issues**: Ensure agents use the `PORT` environment variable correctly

## �🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Resources

- [A2A Protocol Documentation](https://a2a-protocol.org/latest/)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)
- [Azure AI Foundry Documentation](https://docs.microsoft.com/en-us/azure/ai-foundry/)
- [Google ADK Documentation](https://developers.google.com/adk)
- [CrewAI Framework](https://docs.crewai.com/)

## 🆘 Support

For questions and support:
- Open an issue in this repository
- Check the [A2A Protocol documentation](https://a2a-protocol.org/latest/)
- Review the [Azure AI documentation](https://docs.microsoft.com/en-us/azure/ai/)

---

*This demo showcases the power of standardized agent communication protocols in building complex, multi-framework AI systems that can collaborate seamlessly across different platforms and technologies.*