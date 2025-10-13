from azure.storage.blob import BlobServiceClient, generate_blob_sas, generate_container_sas, BlobSasPermissions
from datetime import datetime, timedelta
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging
import os

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_sas_token(container_name: str) -> str:
    """
    Generate a SAS token for a blob in Azure Blob Storage.
    :param container_name: Name of the container.
    """
    blob_service_client = get_blob_client()
    if not blob_service_client:
        raise ValueError("Blob service client could not be created.")
    
    # Ensure container exists
    try:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
            logger.info(f"Created container: {container_name}")
    except Exception as container_error:
        logging.warning(f"Container check/creation failed: {container_error}")

    # Generate SAS token
    
    key_start_time = datetime.utcnow()
    key_expiry_time = key_start_time + timedelta(days=7)  # SAS token valid for 7 days
    
    logger.info("Generating SAS token for container: %s", container_name)
    try:
        user_delegation_key = blob_service_client.get_user_delegation_key(
            key_start_time, key_expiry_time
        )
        
        # Generate SAS token with user delegation key
        sas_token = generate_container_sas(
            account_name=os.environ.get("STORAGE_ACCOUNT_NAME"),
            container_name=container_name,
            user_delegation_key=user_delegation_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.utcnow() + timedelta(days=7),
            start=datetime.utcnow() - timedelta(minutes=5)  # Start 5 minutes ago to account for clock skew
        )

        return sas_token
    
    except Exception as sas_error:
        logging.error(f"Failed to generate SAS token: {sas_error}")
        raise ValueError("Failed to generate SAS token.")

def get_blob_client() -> BlobServiceClient:
    """
    Create a BlobServiceClient for the specified Azure Storage account.
    :param account_name: Azure Storage account name.
    :return: BlobServiceClient instance.
    """
    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    if not storage_account_name:
        # Try to parse from blob service URI
        blob_service_uri = os.environ.get("AzureWebJobsStorage__blobServiceUri")
        if blob_service_uri:
            storage_account_name = blob_service_uri.split("//")[1].split(".")[0]
        else:
            raise ValueError("Storage account name is not configured and could not be parsed from environment variables.")

    account_url = f"https://{storage_account_name}.blob.core.windows.net"   
    client_id = os.environ.get("AZURE_CLIENT_ID")    

    print("Client ID:", client_id)    

    # Check if we're running in Azure (has IMDS endpoint available)
    is_azure_environment = (
        os.environ.get("MSI_ENDPOINT") or 
        os.environ.get("IDENTITY_ENDPOINT") or
        os.environ.get("AZURE_CLIENT_ID")
        #   and (
        #     os.environ.get("WEBSITE_SITE_NAME") or  # App Service
        #     os.environ.get("FUNCTION_APP_URL") or  # Functions
        #     os.environ.get("CONTAINER_APP_NAME")  # Container Apps
        # )
    )

    # Try managed identity only if we're in Azure environment
    if is_azure_environment:
        try:
            if client_id:
                logger.info(f"Attempting user-assigned managed identity: {client_id}")
                print(f"Attempting user-assigned managed identity: {client_id}")
                credential = ManagedIdentityCredential(client_id=client_id)
            else:
                logger.info("Attempting system-assigned managed identity")
                print("Attempting system-assigned managed identity")
                credential = ManagedIdentityCredential()
            
            # Test the credential by trying to create the client AND actually use it
            blob_service_client = BlobServiceClient(account_url, credential=credential)
            
            # Actually test the credential by trying to list containers
            print("Testing managed identity by listing containers...")
            container_list = blob_service_client.list_containers()
            list(container_list)  # Force the iterator to execute
            
            print("Successfully authenticated with managed identity")
            logger.info("Successfully authenticated with managed identity")

            return blob_service_client
            
        except Exception as managed_identity_error:
            logging.warning(f"Managed identity failed: {managed_identity_error}")
            # Continue to DefaultAzureCredential fallback
    else:
        print("Not in Azure environment, skipping managed identity")
        logger.info("Not in Azure environment, skipping managed identity")
        
    # Fallback to DefaultAzureCredential (for local development)
    logger.info("Using DefaultAzureCredential for authentication")
    print("Using DefaultAzureCredential for authentication")
    
    try:
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url, credential=credential)
        logger.info("Successfully authenticated with DefaultAzureCredential")
        print("Successfully authenticated with DefaultAzureCredential")

        return blob_service_client
    except Exception as default_cred_error:
        logging.error(f"All authentication methods failed. Default Credential: {default_cred_error}")
        raise ValueError("Failed to authenticate with Azure Storage")