import logging
import os

import click
import httpx

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from adk_expense_reimbursement_agent import ReimbursementAgent
from agent_executor import ReimbursementAgentExecutor
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_agent_card(host: str, port: int):
    """Returns the Agent Card for the Reimbursement Agent."""
    capabilities = AgentCapabilities(streaming=True)
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
        name='Reimbursement Google ADK Agent',
        description='This agent handles the reimbursement process for the employees given the amount and purpose of the reimbursement.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

    return agent_card

def get_agent_card_with_public_url(public_url : str):
    """Returns the Agent Card for the Reimbursement Agent."""
    capabilities = AgentCapabilities(streaming=True)
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
        name='Reimbursement Google ADK Agent',
        description='This agent handles the reimbursement process for the employees given the amount and purpose of the reimbursement.',
        url=public_url if public_url.endswith('/') else f'{public_url}/',
        version='1.0.0',
        default_input_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=ReimbursementAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

    return agent_card