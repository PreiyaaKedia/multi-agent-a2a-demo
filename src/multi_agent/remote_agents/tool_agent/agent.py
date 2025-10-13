import asyncio
import logging
import os
from collections.abc import AsyncIterable
from typing import Any

from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential
from dotenv import load_dotenv
from pydantic import BaseModel
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from semantic_kernel.connectors.mcp import MCPSsePlugin
# from semantic_kernel.contents import ChatMessageContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# region Response Format


class ResponseFormat(BaseModel):
    """A Response Format model to direct how the model should respond."""

    status: str = 'input_required'
    message: str


# endregion

# region Azure AI Agent with MCP


class SemanticKernelMCPAgent:
    """Wraps Azure AI Agent with MCP plugins to handle various tasks."""

    def __init__(self):
        self.agent = None
        self.thread = None
        self.client = None
        self.credential = None
        self.plugin = None

    async def initialize(self, mcp_url: str = "http://localhost:7071/runtime/webhooks/mcp/sse"):
        """Initialize the agent with Azure credentials and MCP plugin."""
        try:
            # Create Azure credential
            client_id = os.getenv("AZURE_CLIENT_ID")
            if client_id:
                logger.info(f"Using Azure Client ID: {client_id}")
                self.credential = ManagedIdentityCredential(client_id=client_id)
            else:         
                logger.info("Using Default Azure Credential")
                self.credential = DefaultAzureCredential()

            # Create Azure AI client
            self.client = await AzureAIAgent.create_client(credential=self.credential, endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT")).__aenter__()
            
            # Create the MCP plugin
            self.plugin = MCPSsePlugin(
            name="receipts_field_extraction",
            description="Receipts and invoices field extraction tool",
            url=f"https://func-api-zsqp7uodjlobu.azurewebsites.net/runtime/webhooks/mcp/sse?code={os.getenv('azure_function_key')}",
            # headers={"Authorization": "Bearer <token>"}
            headers={"SuperSecret": "123456",
                     "Accept":"text/event-stream"},
                     load_tools=True,
                     timeout=100,
                     sse_read_timeout=10000
        )

            
            # Initialize the plugin
            await self.plugin.__aenter__()
            
            # Create agent definition
            agent_definition = await self.client.agents.create_agent(
                model=os.getenv("model"),
                name="InvoiceExtractionAgent",
                instructions='''You are an expense processing assistant. Your task is to utilize the MCP tool to extract information from receipts and invoices, assisting users with their expense-related queries. Please make sure to cite your sources. Follow these steps:

            Begin by asking the user for the name of the expense report.
            Note that the expense report name corresponds to a storage location in Azure Blob Storage. Use the MCP tool to retrieve invoice links from the specified expense report.
            Use the MCP tool again to extract item details from the provided receipts or invoices. If there are multiple receipts or invoices uploaded against a receipt, process each one sequentially.
            Present the extracted information to the user in a clear, concise format as shown below:

        FORMAT:
        {Date : <date of the receipt or invoice>,
        Vendor : <vendor name>,
        {Items : [
            {   Name : <item name>,
                Description : <item description>,
                Amount : <item amount>,
            },]}''',
            )

            # Create the agent with MCP plugin
            self.agent = AzureAIAgent(
                client=self.client,
                definition=agent_definition,
                plugins=[self.plugin],
            )
            
            logger.info("MCP Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Agent: {e}")
            await self.cleanup()
            raise

    async def invoke(self, user_input: str, session_id: str = None) -> dict[str, Any]:
        """Handle tasks with the Azure AI Agent and MCP plugins.

        Args:
            user_input (str): User input message.
            session_id (str): Unique identifier for the session (optional).

        Returns:
            dict: A dictionary containing the content and task completion status.
        """
        if not self.agent:
            return {
                'is_task_complete': False,
                'require_user_input': True,
                'content': 'Agent not initialized. Please call initialize() first.',
            }

        try:
            responses = []
            async for response in self.agent.invoke(
                messages=user_input,
                thread=self.thread,
            ):
                responses.append(str(response))
                self.thread = response.thread

            content = "\n".join(responses) if responses else "No response received."
            
            return {
                'is_task_complete': True,
                'require_user_input': False,
                'content': content,
            }
        except Exception as e:
            return {
                'is_task_complete': False,
                'require_user_input': True,
                'content': f'Error processing request: {str(e)}',
            }

    async def stream(
        self,
        user_input: str,
        session_id: str = None,
    ) -> AsyncIterable[dict[str, Any]]:
        """Stream responses from the Azure AI Agent with MCP plugins.

        Args:
            user_input (str): User input message.
            session_id (str): Unique identifier for the session (optional).

        Yields:
            dict: A dictionary containing the content and task completion status.
        """
        if not self.agent:
            yield {
                'is_task_complete': False,
                'require_user_input': True,
                'content': 'Agent not initialized. Please call initialize() first.',
            }
            return

        try:
            final_response = ''
            async for response in self.agent.invoke(
                messages=user_input,
                thread=self.thread,
            ):
                self.thread = response.thread
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': str(response),
                }
                final_response += "\n" + str(response)

            # Final completion message
            yield {
                'is_task_complete': True,
                'require_user_input': False,
                'content': final_response,
            }
        except Exception as e:
            yield {
                'is_task_complete': False,
                'require_user_input': True,
                'content': f'Error processing request: {str(e)}',
            }

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.thread:
                await self.thread.delete()
                self.thread = None
                logger.info("Thread deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting thread: {e}")
        
        try:
            if self.agent and self.client:
                await self.client.agents.delete_agent(self.agent.id)
                logger.info("Agent deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting agent: {e}")
        
        try:
            if self.plugin:
                await self.plugin.__aexit__(None, None, None)
                self.plugin = None
                logger.info("MCP plugin cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up MCP plugin: {e}")
        
        try:
            if self.client:
                await self.client.close()
                self.client = None
                logger.info("Client closed successfully")
        except Exception as e:
            logger.error(f"Error closing client: {e}")
        
        try:
            if self.credential:
                await self.credential.close()
                self.credential = None
                logger.info("Credential closed successfully")
        except Exception as e:
            logger.error(f"Error closing credential: {e}")
        
        self.agent = None