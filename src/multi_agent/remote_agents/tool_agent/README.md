## Command to deploy Function App to Azure

1. Create the resource group
az group create --name rg-a2a-mcp-sse-server --location eastus

2. Create a Storage Account for the Function App
az group create --name rg-a2a-mcp-sse-server --location eastus

3. Create a Function App using the Consumption Plan
az functionapp create --resource-group rg-a2a-mcp-sse-server --consumption-plan-location eastus --runtime python --runtime-version 3.12 --functions-version 4 --name func-a2a-mcp-sse-server --storage-account sta2amcpsseserver --os-type Linux

4. Deploy MCP Server code to Azure Function App:
func azure functionapp publish func-a2a-mcp-sse-server