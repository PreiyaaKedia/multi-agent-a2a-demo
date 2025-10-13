import logging

import click
import httpx

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import SemanticKernelMCPAgentExecutor
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)
def main(host, port):
    """Starts the Semantic Kernel MCP Agent server using A2A."""
    httpx_client = httpx.AsyncClient()
    request_handler = DefaultRequestHandler(
        agent_executor=SemanticKernelMCPAgentExecutor(),
        task_store=InMemoryTaskStore(),
        # push_notifier=InMemoryPushNotifier(httpx_client),
    )

    server = A2AStarletteApplication(
        agent_card=get_agent_card(host, port), http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host=host, port=port)


def get_agent_card(host: str, port: int):
    """Returns the Agent Card for the Semantic Kernel MCP Agent."""
    # Build the agent card
    capabilities = AgentCapabilities(streaming=True)
    skill_mcp_tools = AgentSkill(
        id='invoice_extraction_agent',
        name='Invoice Extraction',
        description=(
            'Extracts information from invoices and receipts using Model Context Protocol (MCP) tools.'
        ),
        tags=['invoice', 'receipts'],
        examples=['Extract content from my reimbursement report XYZ',
                  'Extract total amount from invoice_123.json',
                  'Find vendor name in receipt_456.jpg'
        ],
    )

    agent_card = AgentCard(
        name='FoundryInvoiceExtractionAgent',
        description=(
            'This agent helps process invoices, receipts and other expense reports'
        ),
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=capabilities,
        skills=[skill_mcp_tools],
    )

    return agent_card


def get_agent_card_with_public_url(public_url: str):
    """Returns the Agent Card with the correct public URL."""
    # Build the agent card
    capabilities = AgentCapabilities(streaming=True)
    skill_mcp_tools = AgentSkill(
        id='invoice_extraction_agent',
        name='Invoice Extraction',
        description=(
            'Extracts information from invoices and receipts using Model Context Protocol (MCP) tools.'
        ),
        tags=['invoice', 'receipts'],
        examples=['Extract content from my reimbursement report XYZ',
                  'Extract total amount from invoice_123.json',
                  'Find vendor name in receipt_456.jpg'
        ],
    )

    agent_card = AgentCard(
        name='FoundryInvoiceExtractionAgent',
        description=(
            'This agent helps process invoices, receipts and other expense reports'
        ),
        url=public_url if public_url.endswith('/') else f'{public_url}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=capabilities,
        skills=[skill_mcp_tools],
    )

    return agent_card


if __name__ == '__main__':
    main()