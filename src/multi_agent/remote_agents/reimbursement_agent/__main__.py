import logging
import os

import click

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from adk_expense_reimbursement_agent import ReimbursementAgent
from agent_executor import ReimbursementAgentExecutor
from dotenv import load_dotenv
# from timestamp_ext import TimestampExtension


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10005)
def main(host, port):
    try:
        # Check for API key only if Vertex AI is not configured
        if not any([os.getenv('AZURE_API_BASE'), os.getenv('AZURE_API_KEY'), os.getenv('AZURE_API_VERSION'), os.getenv('AZURE_OPENAI_DEPLOYMENT')]):
                raise MissingAPIKeyError(
                    'AZURE OPENAI environment variable not set correctly. Please set AZURE_API_BASE, AZURE_API_KEY, AZURE_API_VERSION, and AZURE_OPENAI_DEPLOYMENT.'
                )

        # hello_ext = TimestampExtension()
        capabilities = AgentCapabilities(
            streaming=True,
            # extensions=[
            #     hello_ext.agent_extension(),
            # ],
        )
        skill = AgentSkill(
            id='process_reimbursement',
            name='Process Reimbursement Tool',
            description='Helps with the reimbursement process for users given the amount and purpose of the reimbursement.',
            tags=['reimbursement'],
            examples=[
                'Can you reimburse me $20 for my lunch with the clients?'
            ],
        )
        agent_card = AgentCard(
            name='Google ADK Reimbursement Agent',
            description='This agent handles the reimbursement process for the employees given the amount and purpose of the reimbursement.',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            default_input_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        agent_executor = ReimbursementAgentExecutor()
        # Use the decorator version of the extension for highest ease of use.
        # agent_executor = hello_ext.wrap_executor(agent_executor)
        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )
        import uvicorn

        uvicorn.run(server.build(), host=host, port=port)
    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)


if __name__ == '__main__':
    main()