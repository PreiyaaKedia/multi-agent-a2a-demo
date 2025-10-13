from dotenv import load_dotenv
import asyncio
import json
import logging
from dotenv import load_dotenv
import os
import subprocess
import webbrowser
from semantic_kernel.agents import CopilotStudioAgent

# Set Edge profile for interactive authentication BEFORE importing or using CopilotStudioAgent
def setup_edge_profile_browser(profile_directory="Profile 1"):
    """Configure browser to use specific Edge profile for authentication
    
    Args:
        profile_directory: Edge profile directory name
            - "Default" for your first profile (shows as "Profile 1" in Edge UI)
            - "Profile 1" for your second profile (shows as "Profile 2" in Edge UI)
    """
    edge_exe = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    
    print(f"Setting up Edge browser to use profile directory: {profile_directory}")
    
    # Create a custom browser command
    browser_cmd = f'"{edge_exe}" --profile-directory="{profile_directory}" --new-window %s'
    
    # Register the custom browser
    webbrowser.register('edge-profile', None, webbrowser.BackgroundBrowser(browser_cmd))
    
    # Set environment variable to use our custom browser
    os.environ['BROWSER'] = 'edge-profile'

# Setup custom browser before any authentication
# Try "Default" if your Work 2 account is in the first profile
# Try "Profile 1" if your Work 2 account is in the second profile
setup_edge_profile_browser("Default")  # Change this to "Profile 1" if needed

# Clear token cache to force account selection
def clear_token_cache():
    """Clear MSAL token cache to force fresh authentication"""
    cache_paths = [
        os.path.join(os.path.dirname(__file__), "bin", "token_cache_interactive.bin"),
        os.path.expanduser("~/.cache/msal_token_cache.bin"),
        os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "msal_token_cache.bin")
    ]
    
    for cache_path in cache_paths:
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                print(f"Cleared token cache: {cache_path}")
            except Exception as e:
                print(f"Failed to clear cache {cache_path}: {e}")

clear_token_cache()

# Force account selection prompt
os.environ['MSAL_PROMPT'] = 'select_account'  # This will force account selection

async def main():
    agent = CopilotStudioAgent(
        name="PhysicsAgent",
        instructions="You help answer questions about physics."
    )

    USER_INPUTS = [
        "Why is the sky blue?",
        "What is the speed of light?",
    ]

    for user_input in USER_INPUTS:
        print(f"# User: {user_input}")
        response = await agent.get_response(messages=user_input)
        print(f"# {response.name}: {response}")

asyncio.run(main())



