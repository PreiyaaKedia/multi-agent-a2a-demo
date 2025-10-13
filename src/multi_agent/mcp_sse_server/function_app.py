from json import tool
import azure.functions as func
import json
import logging
import sys
import tempfile
from pathlib import Path
from datetime import datetime
import base64
import sys
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, get_bearer_token_provider
import os
from datetime import datetime, timedelta
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, ContentSettings
import uuid

# Add current directory to path to import our PDF converter
curr_dir = Path(__file__).parent
sys.path.append(str(curr_dir))

from json_to_pdf_converter import convert_json_to_pdf, parse_blob_url_info, upload_pdf_to_blob
from blob_utils import get_blob_client
from content_understanding_client import AzureContentUnderstandingClient

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_IMAGE_NAME_PROPERTY_NAME = "imagename"
_IMAGE_DATA_PROPERTY_NAME = "imagedata"
_ANALYZER_ID_PROPERTY_NAME = "analyzerid"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"
_IMAGE_BLOB_PATH = "images/{mcptoolargs." + _IMAGE_NAME_PROPERTY_NAME + "}"
_REPORT_NAME = "ReportName"

# Initialize Azure Content Understanding client
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_API_VERSION = os.getenv("AZURE_AI_API_VERSION", "2025-05-01-preview")

# credential = DefaultAzureCredential()
# token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# content_understanding_client = AzureContentUnderstandingClient(
#     endpoint=AZURE_AI_ENDPOINT,
#     api_version=AZURE_AI_API_VERSION,
#     token_provider=token_provider,
# )

class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }
    
# Define the tool properties using the ToolProperty class
tool_properties_save_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."),
    ToolProperty(_SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."),
]

tool_properties_get_snippets_object = [ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet.")]

# Define tool properties for image operations
tool_properties_save_image_object = [
    ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image file without extension."),
    ToolProperty(_IMAGE_DATA_PROPERTY_NAME, "string", "The base64 encoded image data."),
]

tool_properties_get_image_object = [
    ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image file with extension.")]

# Define tool properties for content extraction
tool_properties_extract_content_object = [
    ToolProperty(_ANALYZER_ID_PROPERTY_NAME, "string", "The analyzer ID to use for content extraction (default: 'invoice-extraction-demo')."),
    ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image file with extension to analyze."),
]

tool_properties_extract_blob_urls = [
    ToolProperty(_REPORT_NAME, "string", "The report name prefix to retrieve blob URLs."),
]

# tool_properties_extract_content_from_blob_object = [
#     ToolProperty(_ANALYZER_ID_PROPERTY_NAME, "string", "The analyzer ID to use for content extraction (default: 'invoice-extraction-demo')."),
#     ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image file in blob storage (with extension) to analyze."),
# ]

# Convert the tool properties to JSON strings
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])
tool_properties_save_image_json = json.dumps([prop.to_dict() for prop in tool_properties_save_image_object])
tool_properties_get_image_json = json.dumps([prop.to_dict() for prop in tool_properties_get_image_object])
tool_properties_extract_content_json = json.dumps([prop.to_dict() for prop in tool_properties_extract_content_object])
tool_properties_get_blob_urls_json = json.dumps([prop.to_dict() for prop in tool_properties_extract_blob_urls])

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet",
    description="Retrieve a snippet by name.",
    toolProperties=tool_properties_get_snippets_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    snippet_content = file.read().decode("utf-8")
    logger.info(f"Retrieved snippet: {snippet_content}")
    return snippet_content

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def save_snippet(file: func.Out[str], context) -> str:
    content = json.loads(context)
    snippet_name_from_args = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content_from_args = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name_from_args:
        return "No snippet name provided"

    if not snippet_content_from_args:
        return "No snippet content provided"

    file.set(snippet_content_from_args)
    logger.info(f"Saved snippet: {snippet_content_from_args}")
    return f"Snippet '{snippet_content_from_args}' saved successfully"

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_image",
    description="Save an image to Azure Blob Storage.",
    toolProperties=tool_properties_save_image_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_IMAGE_BLOB_PATH)
def save_image(file: func.Out[bytes], context) -> str:
    """
    Saves an image to Azure Blob Storage.

    Args:
        file (func.Out[bytes]): The output binding to write the image to Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: Success message or error message.
    """
    try:
        content = json.loads(context)
        image_name_from_args = content["arguments"][_IMAGE_NAME_PROPERTY_NAME]
        image_data_from_args = content["arguments"][_IMAGE_DATA_PROPERTY_NAME]

        if not image_name_from_args:
            return "No image name provided"

        if not image_data_from_args:
            return "No image data provided"


        # Decode the base64 image data
        try:
            # Remove data URL prefix if present (e.g., "data:image/png;base64,")
            if image_data_from_args.startswith("data:"):
                image_data_from_args = image_data_from_args.split(",", 1)[1]
            
            image_bytes = base64.b64decode(image_data_from_args)
        except Exception as decode_error:
            logging.error(f"Failed to decode base64 image data: {decode_error}")
            return f"Failed to decode image data: {str(decode_error)}"

        # Save the image bytes to blob storage
        file.set(image_bytes)
        logger.info(f"Saved image: {image_name_from_args}")
        return f"Image '{image_name_from_args}' saved successfully"

    except json.JSONDecodeError as json_error:
        logging.error(f"Failed to parse JSON context: {json_error}")
        return f"Failed to parse input: {str(json_error)}"
    except Exception as e:
        logging.error(f"Error saving image: {e}")
        return f"Error saving image: {str(e)}"
    
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_image",
    description="Retrieve an image by name from Azure Blob Storage.",
    toolProperties=tool_properties_get_image_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_IMAGE_BLOB_PATH)
def get_image(file: func.InputStream, context) -> str:
    """
    Retrieves an image by name from Azure Blob Storage and returns it as base64 encoded data.

    Args:
        file (func.InputStream): The input binding to read the image from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The base64 encoded image data or an error message.
    """
    try:
        content = json.loads(context)
        image_name_from_args = content["arguments"][_IMAGE_NAME_PROPERTY_NAME]

        # Read the image bytes
        image_bytes = file.read()
        
        # Encode to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        logger.info(f"Retrieved image: {image_name_from_args}")
        
        # Return as data URL format
        return f"data:image/{image_name_from_args.split('.')[-1]};base64,{image_base64}"

    except Exception as e:
        logging.error(f"Error retrieving image: {e}")
        return f"Error retrieving image: {str(e)}"
    
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="extract_content_from_file",
    description="Extract structured content from an image file using Azure Content Understanding.",
    toolProperties=tool_properties_extract_content_json,
)
def extract_content_from_file(context) -> str:
    """
    Extracts structured content from an image file using Azure Content Understanding.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing extracted content or error message.
    """
    
    try:
        # Get endpoint from environment variables with fallback
        endpoint = os.getenv("AZURE_AI_ENDPOINT", "https://azure-ai-agents-demo.cognitiveservices.azure.com/")
        api_version = os.getenv("AZURE_AI_API_VERSION", "2025-05-01-preview")
        
        logger.info(f"Initializing Content Understanding client with endpoint: {endpoint}")
        
        # Initialize authentication - prefer API key for external services
        content_understanding_client = None
        api_key = os.getenv("AZURE_AI_KEY_", None)
        
        logger.info(f"Environment check - AZURE_AI_KEY: {'Present' if api_key else 'Missing'}")
        
        # Force API key usage for external services
        if api_key:
            logger.info("FORCING API key authentication for external AI service (azure-ai-agents-demo)")
            content_understanding_client = AzureContentUnderstandingClient(
                endpoint=endpoint,
                api_version=api_version,
                subscription_key=api_key,
            )
            logger.info("Successfully initialized with API key - external service")
        else:
            # Try managed identity for services in our subscription
            try:
                client_id = os.getenv("AZURE_CLIENT_ID")
                if client_id:
                    logger.info(f"Attempting managed identity auth with client ID: {client_id}")
                    credential = ManagedIdentityCredential(client_id=client_id)
                else:
                    logger.info("Attempting default managed identity auth")
                    credential = ManagedIdentityCredential()
                
                token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
                
                content_understanding_client = AzureContentUnderstandingClient(
                    endpoint=endpoint,
                    api_version=api_version,
                    token_provider=token_provider,
                )
                logger.info("Successfully initialized with ManagedIdentityCredential")
                
            except Exception as managed_identity_error:
                logging.warning(f"Managed identity failed: {managed_identity_error}")
                
                # Try DefaultAzureCredential (for local development)
                try:
                    logger.info("Attempting DefaultAzureCredential")
                    credential = DefaultAzureCredential()
                    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
                    
                    content_understanding_client = AzureContentUnderstandingClient(
                        endpoint=endpoint,
                        api_version=api_version,
                        token_provider=token_provider,
                    )
                    logger.info("Successfully initialized with DefaultAzureCredential")
                    
                except Exception as default_cred_error:
                    logging.warning(f"DefaultAzureCredential failed: {default_cred_error}")
                    
                    # Final fallback to API key
                    if api_key:
                        logger.info("Using API key authentication as final fallback")
                        content_understanding_client = AzureContentUnderstandingClient(
                            endpoint=endpoint,
                            api_version=api_version,
                            subscription_key=api_key,
                        )
                        logger.info("Successfully initialized with API key fallback")
                    else:
                        raise Exception(f"All authentication methods failed. No API key available. Managed Identity: {managed_identity_error}, Default Credential: {default_cred_error}")

        if not content_understanding_client:
            raise Exception("Failed to initialize Content Understanding client with any authentication method")
    except Exception as init_error:
        logging.error(f"Failed to initialize Content Understanding client: {init_error}")
        return json.dumps({"error": f"Failed to initialize client: {str(init_error)}"})

    try:
        content = json.loads(context)
        analyzer_id = content["arguments"].get(_ANALYZER_ID_PROPERTY_NAME, "invoice-extraction-demo")
        image_name = content["arguments"][_IMAGE_NAME_PROPERTY_NAME]

        if not image_name:
            return json.dumps({"error": "No image name provided"})

        # Construct the blob URL for Azure Content Understanding
        # Get storage account name from connection string or environment
        storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME")
        if not storage_account_name:
            # Try to extract from AzureWebJobsStorage connection string
            storage_conn = os.getenv("AzureWebJobsStorage", "")
            if "AccountName=" in storage_conn:
                storage_account_name = storage_conn.split("AccountName=")[1].split(";")[0]
            else:
                return json.dumps({"error": "Could not determine storage account name"})
        
        # Construct the blob URL
        blob_url = f"https://{storage_account_name}.blob.core.windows.net/images/{image_name}"
        logger.info(f"Using blob URL for analysis: {blob_url}")

        # Use the content understanding client to extract content
        response = content_understanding_client.begin_analyze(analyzer_id, file_location=blob_url)
        result_json = content_understanding_client.poll_result(response)
        extracted_result_json = result_json['result']['contents'][0]
        
        items = []
        vendor_name = ""

        logger.info(f"Extracted Result JSON: {json.dumps(extracted_result_json, indent=2)}")
        
        if "fields" in extracted_result_json:
            extracted_fields = extracted_result_json['fields']
            for field_name, field_value in extracted_fields.items():
                if isinstance(field_value, dict) and 'valueString' in field_value:
                    vendor_name = field_value.get('valueString', '')
                elif isinstance(field_value, dict) and field_value.get('type') == 'array':
                    for array_item in field_value.get('valueArray', []):
                        if 'valueObject' in array_item:
                            value_obj = array_item['valueObject']
                            item = {"vendorName": vendor_name}
                            
                            # Extract description if available
                            if 'Description' in value_obj and 'valueString' in value_obj['Description']:
                                item["item_description"] = value_obj['Description']['valueString']
                            
                            # Extract amount if available
                            if 'Amount' in value_obj and 'valueNumber' in value_obj['Amount']:
                                item["amount"] = value_obj['Amount']['valueNumber']
                            
                            items.append(item)

        result = {
            "analyzer_id": analyzer_id,
            "file_location": blob_url,
            "vendor_name": vendor_name,
            "extracted_items": items,
            # "raw_result": extracted_result_json
        }

        logger.info(f"Successfully extracted content from {blob_url} using analyzer {analyzer_id}")
        logger.info(f"Extracted items: {json.dumps(items, indent=2)}")
        return json.dumps(result, indent=2)

    except json.JSONDecodeError as json_error:
        logging.error(f"Failed to parse JSON context: {json_error}")
        return json.dumps({"error": f"Failed to parse input: {str(json_error)}"})
    except Exception as e:
        logging.error(f"Error extracting content: {e}")
        return json.dumps({"error": f"Error extracting content: {str(e)}"})
    
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_blob_urls_from_container",
    description="Get all blob URLs from a specific container in Azure Blob Storage with optional prefix filter.",
    toolProperties=tool_properties_get_blob_urls_json,
)
def get_blob_urls_from_container(context) -> str:
    """
    Retrieves all blob URLs from a specific container in Azure Blob Storage with optional prefix filter.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing blob URLs or error message.
    """
    from azure.storage.blob import BlobServiceClient
    from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

    try:
        content = json.loads(context)
        prefix = content["arguments"][_REPORT_NAME]
        max_results = content["arguments"].get("max_results", 100)

        # logger.info(f"Retrieving blob URLs with prefix '{prefix}' and max results {max_results}")
        # # Get storage account name from environment
        storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME")
        if not storage_account_name:
            # Try to parse from AzureWebJobsStorage connection string
            storage_conn = os.getenv("AzureWebJobsStorage", "")
            if "AccountName=" in storage_conn:
                storage_account_name = storage_conn.split("AccountName=")[1].split(";")[0]
            else:
                return json.dumps({"error": "Could not determine storage account name"})

        # # Create blob service client with user-assigned managed identity
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        blob_service_client = get_blob_client()

        # Collect all blob URLs from the specified container
        container_name = "images"
        blob_urls = []

        try:
            container_client = blob_service_client.get_container_client(container_name)

            for blob in container_client.list_blobs(
                name_starts_with=prefix,
                results_per_page=max_results
            ):
                blob_urls.append(f"{account_url}/{container_name}/{blob.name}")
            logger.info(f"Retrieved {len(blob_urls)} blob URLs from container '{container_name}' with prefix '{prefix}'")
            return json.dumps({"blob_urls": blob_urls})
        
        except Exception as container_error:
            logging.error(f"Failed to list blobs in container '{container_name}': {container_error}")
            return json.dumps({"error": f"Failed to list blobs: {str(container_error)}"})
        
    except Exception as e:
        logging.error(f"Error retrieving blob URLs: {e}")
        return json.dumps({"error": f"Error retrieving blob URLs: {str(e)}"})

# === OPTIMIZED IMAGE UPLOAD FUNCTIONS ===
# Add these imports at the top if not already present
# from datetime import datetime, timedelta
# from azure.storage.blob import generate_blob_sas, BlobSasPermissions

# Optimized MCP-Compatible Save Image with chunked processing
@app.function_name(name="save_image_optimized")
@app.route(route="save_image_optimized", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
@app.blob_output(arg_name="file", path="images/{imagename}", connection="AzureWebJobsStorage")
def save_image_optimized(req: func.HttpRequest, file: func.Out[bytes]) -> str:
    """
    MCP-compatible but optimized version with streaming and memory management
    """
    import gc
    try:
        # Parse MCP request
        content = json.loads(req.get_body().decode('utf-8'))
        
        image_name_from_args = content["arguments"]["imagename"]
        image_data_from_args = content["arguments"]["imagedata"]
        
        logger.info(f"Processing optimized image: {image_name_from_args}")
        
        # Memory-efficient base64 decoding for large images
        if image_data_from_args.startswith("data:"):
            # Remove data URI prefix
            image_data_from_args = image_data_from_args.split(",", 1)[1]
        
        # Decode in chunks to reduce memory usage
        chunk_size = 1024 * 1024  # 1MB chunks
        decoded_chunks = []
        
        for i in range(0, len(image_data_from_args), chunk_size):
            chunk = image_data_from_args[i:i + chunk_size]
            decoded_chunks.append(base64.b64decode(chunk))
        
        # Combine chunks
        image_bytes = b''.join(decoded_chunks)
        
        # Clear intermediate data from memory
        del decoded_chunks
        del image_data_from_args
        gc.collect()
        
        # Save to blob storage
        file.set(image_bytes)
        
        # Clear final data from memory
        del image_bytes
        gc.collect()
        
        logger.info(f"Optimized save completed: {image_name_from_args}")
        return f"Image '{image_name_from_args}' saved successfully (optimized)"
        
    except Exception as e:
        logging.error(f"Optimized save failed: {str(e)}")
        gc.collect()
        return f"Error saving image: {str(e)}"


@app.route(route="generate_upload_sas", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def generate_upload_sas(req: func.HttpRequest) -> func.HttpResponse:
    """
    Generate a SAS URL for direct browser-to-blob upload using user delegation SAS
    No file content goes through Azure Functions - just authentication
    """
    from datetime import datetime, timedelta
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, UserDelegationKey
    from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
    import uuid
    
    try:
        # Parse request
        req_body = req.get_json()
        filename = req_body.get('filename', f"{uuid.uuid4()}.png")
        content_type = req_body.get('content_type', 'image/png')
        
        # Support folder prefix for organizing files
        # If filename contains a path (e.g., "invoices-2025/invoice1.pdf"), preserve it
        # This allows organizing files in virtual folders within the container
        
        # Get storage account name from environment
        storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
        if not storage_account_name:
            # Try to parse from blob service URI
            blob_service_uri = os.environ.get("AzureWebJobsStorage__blobServiceUri")
            if blob_service_uri:
                storage_account_name = blob_service_uri.split("//")[1].split(".")[0]
        
        if not storage_account_name:
            return func.HttpResponse(
                json.dumps({"error": "Storage account not configured"}), 
                status_code=500, 
                mimetype="application/json"
            )
        
        # Create blob service client with user-assigned managed identity
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        # Use user-assigned managed identity with fallback for local development
        client_id = os.environ.get("AZURE_CLIENT_ID")
        credential = None
        
        try:
            if client_id:
                logger.info(f"Attempting user-assigned managed identity: {client_id}")
                credential = ManagedIdentityCredential(client_id=client_id)
            else:
                logger.info("Attempting system-assigned managed identity")
                credential = ManagedIdentityCredential()
            
            # Test the credential by trying to create the client
            blob_service_client = BlobServiceClient(account_url, credential=credential)
            logger.info("Successfully authenticated with managed identity")
            
        except Exception as managed_identity_error:
            logging.warning(f"Managed identity failed: {managed_identity_error}")
            logger.info("Falling back to DefaultAzureCredential for local development")
            
            try:
                credential = DefaultAzureCredential()
                blob_service_client = BlobServiceClient(account_url, credential=credential)
                logger.info("Successfully authenticated with DefaultAzureCredential")
            except Exception as default_cred_error:
                logging.error(f"All authentication methods failed. Managed Identity: {managed_identity_error}, Default Credential: {default_cred_error}")
                return func.HttpResponse(
                    json.dumps({"error": f"Authentication failed: {str(default_cred_error)}"}), 
                    status_code=500, 
                    mimetype="application/json"
                )
        
        container_name = "images"
        blob_name = filename
        
        # Ensure container exists
        try:
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {container_name}")
        except Exception as container_error:
            logging.warning(f"Container check/creation failed: {container_error}")
        
        # Get user delegation key for generating SAS with managed identity
        key_start_time = datetime.utcnow()
        key_expiry_time = key_start_time + timedelta(hours=1)
        
        try:
            user_delegation_key = blob_service_client.get_user_delegation_key(
                key_start_time, key_expiry_time
            )
            
            # Generate SAS token with user delegation key
            sas_token = generate_blob_sas(
                account_name=storage_account_name,
                container_name=container_name,
                blob_name=blob_name,
                user_delegation_key=user_delegation_key,
                permission=BlobSasPermissions(write=True, create=True),
                expiry=datetime.utcnow() + timedelta(hours=1),
                start=datetime.utcnow() - timedelta(minutes=5)  # Start 5 minutes ago to account for clock skew
            )
            
            # Create the full SAS URL
            sas_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
            
            logger.info(f"Generated SAS URL for: {filename}")
            
            return func.HttpResponse(
                json.dumps({
                    "upload_url": sas_url,
                    "storage_account": storage_account_name,
                    "container": container_name,
                    "filename": filename,
                    "content_type": content_type,
                    "expires_in": "1 hour",
                    "upload_method": "PUT",
                    "headers": {
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": content_type
                    }
                }),
                mimetype="application/json"
            )
            
        except Exception as delegation_error:
            # Fallback: If user delegation fails, provide alternative method
            logging.warning(f"User delegation key failed: {delegation_error}")
            
            blob_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}"
            
            return func.HttpResponse(
                json.dumps({
                    "error": "SAS generation not available with current permissions",
                    "blob_url": blob_url,
                    "alternative_endpoint": "/api/upload_image_direct",
                    "note": "Use upload_image_direct endpoint for secure uploads through the function",
                    "delegation_error": str(delegation_error)
                }),
                mimetype="application/json",
                status_code=200  # Not a failure, just a limitation
            )
        
    except Exception as e:
        logging.error(f"SAS generation failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"SAS generation failed: {str(e)}"}), 
            status_code=500, 
            mimetype="application/json"
        )


# Direct Binary Upload (Alternative to MCP)
@app.route(route="upload_image_direct", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def upload_image_direct(req: func.HttpRequest) -> func.HttpResponse:
    """
    Optimized image upload - accepts raw binary data
    Content-Type: image/png, image/jpeg, etc.
    Supports custom filename via query parameter or header
    """
    from azure.storage.blob import BlobServiceClient
    import uuid
    
    try:
        # Get image data as bytes directly (no base64 conversion needed)
        image_data = req.get_body()
        
        if not image_data:
            return func.HttpResponse(
                json.dumps({"error": "No image data provided"}), 
                status_code=400, 
                mimetype="application/json"
            )
        
        # Get filename from query parameters, headers, or generate unique one
        custom_filename = req.params.get('filename') or req.headers.get('X-Filename')
        if custom_filename:
            # Support folder prefixes in filename (e.g., "invoices-2025/invoice1.pdf")
            image_name = custom_filename
        else:
            # Generate unique filename as fallback
            image_name = f"{uuid.uuid4()}.png"
        
        # Get storage connection using user-assigned managed identity with fallback
        from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
        
        # Get storage account name from environment
        storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
        if not storage_account_name:
            # Try to parse from blob service URI
            blob_service_uri = os.environ.get("AzureWebJobsStorage__blobServiceUri")
            if blob_service_uri:
                storage_account_name = blob_service_uri.split("//")[1].split(".")[0]
        
        if not storage_account_name:
            return func.HttpResponse(
                json.dumps({"error": "Storage account not configured"}), 
                status_code=500, 
                mimetype="application/json"
            )
        
        # Create blob service client with user-assigned managed identity
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        # Use user-assigned managed identity with fallback for local development
        client_id = os.environ.get("AZURE_CLIENT_ID")
        credential = None
        
        try:
            if client_id:
                logger.info(f"Attempting user-assigned managed identity: {client_id}")
                credential = ManagedIdentityCredential(client_id=client_id)
            else:
                logger.info("Attempting system-assigned managed identity")
                credential = ManagedIdentityCredential()
            
            # Test the credential by trying to create the client
            blob_service_client = BlobServiceClient(account_url, credential=credential)
            logger.info("Successfully authenticated with managed identity")
            
        except Exception as managed_identity_error:
            logging.warning(f"Managed identity failed: {managed_identity_error}")
            logger.info("Falling back to DefaultAzureCredential for local development")
            
            try:
                credential = DefaultAzureCredential()
                blob_service_client = BlobServiceClient(account_url, credential=credential)
                logger.info("Successfully authenticated with DefaultAzureCredential")
            except Exception as default_cred_error:
                logging.error(f"All authentication methods failed. Managed Identity: {managed_identity_error}, Default Credential: {default_cred_error}")
                return func.HttpResponse(
                    json.dumps({"error": f"Authentication failed: {str(default_cred_error)}"}), 
                    status_code=500, 
                    mimetype="application/json"
                )
        
        # Upload directly to blob storage (streaming)
        container_name = "images"
        blob_client = blob_service_client.get_blob_client(
            container=container_name, 
            blob=image_name
        )
        
        # Get content type from request headers or determine from filename
        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        if content_type == 'application/octet-stream' and image_name:
            # Try to determine content type from file extension
            if image_name.lower().endswith('.png'):
                content_type = 'image/png'
            elif image_name.lower().endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif image_name.lower().endswith('.pdf'):
                content_type = 'application/pdf'
        
        # Stream upload - memory efficient for large files
        blob_client.upload_blob(
            image_data, 
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type=content_type)
        )
        
        logger.info(f"Successfully uploaded {image_name} ({len(image_data)} bytes)")
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "filename": image_name,
                "size_bytes": len(image_data),
                "blob_url": blob_client.url
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Upload failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Upload failed: {str(e)}"}), 
            status_code=500, 
            mimetype="application/json"
        )

# @app.function_name(name="prepare_expense_report")
# @app.queue_trigger(arg_name="inputQueue", queue_name="input", connection="DEPLOYMENT_STORAGE_CONNECTION_STRING")
# @app.queue_output(arg_name="outputQueue", queue_name="output", connection="DEPLOYMENT_STORAGE_CONNECTION_STRING")
@app.route(route="json_to_pdf", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def prepare_expense_report(req : func.HttpRequest) -> func.HttpResponse:
    """
    Convert JSON reimbursement data to PDF report with invoice images.
    
    Accepts:
    - JSON data with Summary and Details fields
    - Each detail item can have an invoice_link for image inclusion
    
    Returns:
    - PDF download URL in Azure Blob Storage (same container/prefix as invoice links)
    """
    
    try:
        # Parse JSON request
        req_body = json.loads(req.get_body())
        # req_body = json.loads(inputQueue.get_body().decode('utf-8'))
        # correlation_id = req_body['CorrelationId']
        # req_body.pop('CorrelationId', None)  # Remove CorrelationId from body
        
        # logger.info(f"Processing reimbursement report request with CorrelationId: {correlation_id}")
        
        if not req_body:
            logger.error("No JSON data provided in queue message")
            return {"status": "error", "message": "No JSON data provided"}

        # Validate required fields
        if "Summary" not in req_body or "Details" not in req_body:
            logger.error("JSON must contain 'Summary' and 'Details' fields")
            return {"status": "error", "message": "Invalid JSON structure"}

        
        # Optional parameters - since this is queue triggered, generate filename automatically
        # filename = req.params.get('filename')  # Not available in queue trigger
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reimbursement_report_{timestamp}.pdf"
        
        # Ensure filename ends with .pdf
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        logger.info(f"Generating PDF report: {filename}")
        logger.info(f"Input data contains {len(req_body.get('Details', []))} items")
        
        # Determine container and prefix from the first invoice_link
        container_name = "images"  # Default
        blob_prefix = ""  # Default
        
        details = req_body.get('Details', [])
        if details:
            for item in details:
                invoice_link = item.get('invoice_link')
                if invoice_link:
                    container_name, blob_prefix = parse_blob_url_info(invoice_link)
                    logger.info(f"Using container: {container_name}, prefix: {blob_prefix}")
                    break
        
        # Create temporary file for PDF generation
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Generate PDF using the direct function call
            pdf_output_path = convert_json_to_pdf(req_body, temp_path)
            
            logger.info(f"PDF generated successfully at: {pdf_output_path}")
            
            # Upload to blob storage in the same container/prefix as invoice links
            blob_url = upload_pdf_to_blob(pdf_output_path, container_name, blob_prefix, filename)
            
            # Get file size for response
            # file_size = os.path.getsize(pdf_output_path)
            
            # Clean up temporary file
            os.unlink(temp_path)

            # response = {"status" : "success",
            #             "report_link": blob_url,
            #             "CorrelationId": correlation_id}
            
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "report_link": blob_url,
                    # "container": container_name,
                    "prefix": blob_prefix,
                    # "size_bytes": file_size,
                    # "items_processed": len(details)
                }),
                mimetype="application/json"
            )
        
            # outputQueue.set(json.dumps(response).encode("utf-8"))
            # logger.info(f"PDF report uploaded successfully: {blob_url}")
            # return response
                
        except Exception as pdf_error:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            logger.error(f"PDF generation failed: {pdf_error}")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": str(pdf_error)
                }),
                mimetype="application/json"
            )
            # outputQueue.set(json.dumps({
            #     "status": "error",
            #     "message": str(pdf_error),
            #     "CorrelationId": correlation_id
            # }).encode("utf-8"))

    except Exception as e:
        logging.error(f"PDF generation failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",  
                "message": str(e)
            }),
            mimetype="application/json"
        )
        # outputQueue.set(json.dumps({
        #     "status": "error",
        #     "message": str(e),
        #     "CorrelationId": correlation_id
        # }).encode("utf-8"))






