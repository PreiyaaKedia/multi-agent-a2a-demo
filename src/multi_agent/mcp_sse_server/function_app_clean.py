import azure.functions as func
import datetime
import json
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint."""
    logging.info('Health check endpoint was triggered.')
    
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "message": "MCP SSE Server is running"
        }),
        status_code=200,
        mimetype="application/json"
    )

@app.route(route="test", auth_level=func.AuthLevel.ANONYMOUS)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    """Simple test function to verify deployment is working."""
    logging.info('Test function processed a request.')
    
    return func.HttpResponse(
        json.dumps({
            "status": "success",
            "message": "MCP Function App is deployed and running",
            "timestamp": datetime.datetime.now().isoformat(),
            "python_version": "3.12"
        }),
        status_code=200,
        mimetype="application/json"
    )
