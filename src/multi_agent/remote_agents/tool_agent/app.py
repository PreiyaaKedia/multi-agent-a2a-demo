import os

# ...existing code...
from main import get_agent_card, get_agent_card_with_public_url
from agent_executor import SemanticKernelMCPAgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.apps import A2AStarletteApplication

# Configure handler and build the ASGI app
request_handler = DefaultRequestHandler(
    agent_executor=SemanticKernelMCPAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

# Port/host configuration. App Service provides $PORT.
HOST = os.getenv("A2A_HOST", "0.0.0.0")
PORT = int(os.getenv("A2A_PORT", os.getenv("PORT", 8000)))

# Get the public URL for the agent card
PUBLIC_URL = os.getenv("A2A_PUBLIC_URL", "https://dev-toolagent-web.azurewebsites.net")

server = A2AStarletteApplication(
    agent_card=get_agent_card_with_public_url(PUBLIC_URL), http_handler=request_handler
)

# ASGI callable expected by Gunicorn/Uvicorn
app = server.build()
