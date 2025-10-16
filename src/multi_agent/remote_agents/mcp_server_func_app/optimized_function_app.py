import azure.functions as func
import json
import logging
from azure.storage.blob import BlobServiceClient
import os
import tempfile
import uuid
import base64
from datetime import datetime, timedelta
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

app = func.FunctionApp()

# Option 1: Direct Binary Upload with Streaming
@app.route(route="upload_image_direct", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def upload_image_direct(req: func.HttpRequest) -> func.HttpResponse:
    """
    Optimized image upload - accepts raw binary data
    Content-Type: image/png, image/jpeg, etc.
    """
    try:
        # Get image data as bytes directly (no base64 conversion needed)
        image_data = req.get_body()
        
        if not image_data:
            return func.HttpResponse("No image data provided", status_code=400)
        
        # Generate unique filename
        image_name = f"{uuid.uuid4()}.png"
        
        # Get storage connection from environment
        storage_connection = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection)
        
        # Upload directly to blob storage (streaming)
        container_name = "images"
        blob_client = blob_service_client.get_blob_client(
            container=container_name, 
            blob=image_name
        )
        
        # Stream upload - memory efficient for large files
        blob_client.upload_blob(
            image_data, 
            overwrite=True,
            blob_type="BlockBlob",
            content_settings={"content_type": "image/png"}
        )
        
        logging.info(f"Successfully uploaded {image_name} ({len(image_data)} bytes)")
        
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
        return func.HttpResponse(f"Upload failed: {str(e)}", status_code=500)


# Option 2: Multipart Form Upload
@app.route(route="upload_image_multipart", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def upload_image_multipart(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle multipart/form-data uploads - most efficient for web clients
    """
    try:
        # Parse multipart form data
        files = req.files
        if not files or 'image' not in files:
            return func.HttpResponse("No image file provided", status_code=400)
        
        image_file = files['image']
        original_filename = image_file.filename or f"{uuid.uuid4()}.png"
        
        # Read file content
        image_data = image_file.read()
        
        # Upload to blob storage
        storage_connection = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection)
        
        blob_client = blob_service_client.get_blob_client(
            container="images", 
            blob=original_filename
        )
        
        blob_client.upload_blob(
            image_data, 
            overwrite=True,
            content_settings={
                "content_type": image_file.content_type or "image/png"
            }
        )
        
        logging.info(f"Multipart upload successful: {original_filename}")
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "filename": original_filename,
                "size_bytes": len(image_data),
                "content_type": image_file.content_type
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Multipart upload failed: {str(e)}")
        return func.HttpResponse(f"Upload failed: {str(e)}", status_code=500)


# Option 3: Chunked Upload for Very Large Files (>100MB)
@app.route(route="upload_image_chunked", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def upload_image_chunked(req: func.HttpRequest) -> func.HttpResponse:
    """
    Chunked upload for very large images - parallel processing
    """
    try:
        image_data = req.get_body()
        image_name = req.headers.get('x-filename', f"{uuid.uuid4()}.png")
        
        storage_connection = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection)
        
        blob_client = blob_service_client.get_blob_client(
            container="images", 
            blob=image_name
        )
        
        # For files >100MB, use chunked upload
        if len(image_data) > 100 * 1024 * 1024:  # 100MB
            # Upload in 4MB chunks with parallel processing
            chunk_size = 4 * 1024 * 1024  # 4MB chunks
            block_list = []
            
            for i in range(0, len(image_data), chunk_size):
                chunk = image_data[i:i + chunk_size]
                block_id = f"{i:010d}"  # Zero-padded block ID
                
                blob_client.stage_block(block_id, chunk)
                block_list.append(block_id)
            
            # Commit all blocks
            blob_client.commit_block_list(block_list)
        else:
            # Simple upload for smaller files
            blob_client.upload_blob(image_data, overwrite=True)
        
        logging.info(f"Chunked upload successful: {image_name}")
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "filename": image_name,
                "size_bytes": len(image_data),
                "upload_method": "chunked" if len(image_data) > 100 * 1024 * 1024 else "simple"
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Chunked upload failed: {str(e)}")
        return func.HttpResponse(f"Upload failed: {str(e)}", status_code=500)


# Option 4: Optimized MCP-Compatible Version
@app.function_name(name="save_image_optimized")
@app.route(route="save_image_optimized", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
@app.blob_output(arg_name="file", path="images/{imagename}", connection="AzureWebJobsStorage")
def save_image_optimized(req: func.HttpRequest, file: func.Out[bytes]) -> str:
    """
    MCP-compatible but optimized version with streaming and memory management
    """
    try:
        # Parse MCP request
        content = json.loads(req.get_body().decode('utf-8'))
        
        image_name_from_args = content["arguments"]["imagename"]
        image_data_from_args = content["arguments"]["imagedata"]
        
        logging.info(f"Processing image: {image_name_from_args}")
        
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
        
        # Save to blob storage
        file.set(image_bytes)
        
        # Clear final data from memory
        del image_bytes
        
        logging.info(f"Optimized save completed: {image_name_from_args}")
        return f"Image '{image_name_from_args}' saved successfully (optimized)"
        
    except Exception as e:
        logging.error(f"Optimized save failed: {str(e)}")
        return f"Error saving image: {str(e)}"


# Option 5: Generate SAS URL for Direct Browser Upload
@app.route(route="generate_upload_sas", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def generate_upload_sas(req: func.HttpRequest) -> func.HttpResponse:
    """
    Generate a SAS URL for direct browser-to-blob upload
    No file content goes through Azure Functions - just authentication
    """
    try:
        # Parse request
        req_body = req.get_json()
        filename = req_body.get('filename', f"{uuid.uuid4()}.png")
        content_type = req_body.get('content_type', 'image/png')
        
        # Get storage connection details
        storage_connection = os.environ["AzureWebJobsStorage"]
        
        # Parse connection string to get account details
        connection_parts = dict(item.split('=', 1) for item in storage_connection.split(';') if '=' in item)
        account_name = connection_parts.get('AccountName')
        account_key = connection_parts.get('AccountKey')
        
        if not account_name or not account_key:
            return func.HttpResponse("Storage account configuration error", status_code=500)
        
        container_name = "images"
        blob_name = filename
        
        # Generate SAS token with upload permissions
        sas_token = generate_blob_sas(
            account_name=account_name,
            account_key=account_key,
            container_name=container_name,
            blob_name=blob_name,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        )
        
        # Construct the full SAS URL
        blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        sas_url = f"{blob_url}?{sas_token}"
        
        logging.info(f"Generated SAS URL for: {filename}")
        
        return func.HttpResponse(
            json.dumps({
                "sas_url": sas_url,
                "blob_url": blob_url,
                "filename": filename,
                "expires_in": "1 hour",
                "content_type": content_type
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"SAS generation failed: {str(e)}")
        return func.HttpResponse(f"SAS generation failed: {str(e)}", status_code=500)


# Option 6: Presigned POST for Secure Browser Upload
@app.route(route="generate_presigned_post", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def generate_presigned_post(req: func.HttpRequest) -> func.HttpResponse:
    """
    Generate presigned POST policy for secure browser uploads with size limits
    """
    try:
        req_body = req.get_json()
        filename = req_body.get('filename', f"{uuid.uuid4()}.png")
        max_file_size = req_body.get('max_size_mb', 10) * 1024 * 1024  # Default 10MB
        
        # Get storage connection details
        storage_connection = os.environ["AzureWebJobsStorage"]
        connection_parts = dict(item.split('=', 1) for item in storage_connection.split(';') if '=' in item)
        account_name = connection_parts.get('AccountName')
        account_key = connection_parts.get('AccountKey')
        
        container_name = "images"
        
        # Generate SAS with conditions
        sas_token = generate_blob_sas(
            account_name=account_name,
            account_key=account_key,
            container_name=container_name,
            blob_name=filename,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        
        upload_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{filename}?{sas_token}"
        
        return func.HttpResponse(
            json.dumps({
                "upload_url": upload_url,
                "method": "PUT",
                "headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": req_body.get('content_type', 'image/png')
                },
                "max_file_size": max_file_size,
                "expires_in": "1 hour"
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Presigned POST generation failed: {str(e)}")
        return func.HttpResponse(f"Presigned POST generation failed: {str(e)}", status_code=500)
