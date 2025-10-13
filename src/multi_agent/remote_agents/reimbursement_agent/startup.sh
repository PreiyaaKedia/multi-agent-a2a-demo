#!/usr/bin/env bash
# Startup helper used locally or in App Service if you prefer a script instead of configuring the startup command.
# It uses $PORT so App Service can route traffic correctly.

PORT=${PORT:-8000}

# Use uvicorn directly - matches local testing setup
uvicorn app:app --host 0.0.0.0 --port ${PORT}