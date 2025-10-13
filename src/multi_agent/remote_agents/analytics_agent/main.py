"""This file serves as the main entry point for the application.

It initializes the A2A server, defines the agent's capabilities,
and starts the server to handle incoming requests. Notice the agent runs on port 10011.
"""

import logging

import click
import httpx

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent import ChartGenerationAgent
from agent_executor import ChartGenerationAgentExecutor
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_agent_card(host: str, port: int):
    """Returns the Agent Card for the Chart Generation Agent."""
    capabilities = AgentCapabilities(streaming=False)
    skill = AgentSkill(
        id='chart_generator',
        name='Chart Generator',
        description='Generate a chart based on CSV-like data passed in',
        tags=['generate image', 'edit image'],
        examples=[
            'Generate a chart of revenue: Jan,$1000 Feb,$2000 Mar,$1500'
        ],
    )

    agent_card = AgentCard(
        name='Chart Generator CrewAI Agent',
        description='Generate charts from structured CSV-like data input.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=ChartGenerationAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=ChartGenerationAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

    return agent_card

def get_agent_card_with_public_url(public_url: str):
    """Returns the Agent Card for the Chart Generation Agent."""
    capabilities = AgentCapabilities(streaming=False)
    skill = AgentSkill(
        id='chart_generator',
        name='Chart Generator',
        description='Generate a chart based on CSV-like data passed in',
        tags=['generate image', 'edit image'],
        examples=[
            'Generate a chart of revenue: Jan,$1000 Feb,$2000 Mar,$1500'
        ],
    )

    agent_card = AgentCard(
        name='Chart Generator CrewAI Agent',
        description='Generate charts from structured CSV-like data input.',
        url=public_url if public_url.endswith('/') else f'{public_url}/',
        version='1.0.0',
        default_input_modes=ChartGenerationAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=ChartGenerationAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

    return agent_card
