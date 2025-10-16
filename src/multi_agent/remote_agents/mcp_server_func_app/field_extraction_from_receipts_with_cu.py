import uuid
import logging
import json
import os
import sys
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

curr_dir = Path.cwd()
sys.path.append(str(curr_dir))
from content_understanding_client import AzureContentUnderstandingClient

load_dotenv(find_dotenv())

AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_API_VERSION = os.getenv("AZURE_AI_API_VERSION", "2025-05-01-preview")

# extraction_templates = {
#     "receipt": ("./data/invoice.json", "./data/invoice.png")
# }

# ANALYZER_TEMPLATE = "receipt"

# (analyzer_template_path, analyzer_sample_file_path) = extraction_templates[ANALYZER_TEMPLATE]

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

client = AzureContentUnderstandingClient(
    endpoint=AZURE_AI_ENDPOINT,
    api_version=AZURE_AI_API_VERSION,
    token_provider=token_provider,
    # x_ms_useragent="azure-ai-content-understanding-python/field_extraction", # This header is used for sample usage telemetry, please comment out this line if you want to opt out.
)

## Create custom analyzer to extract fields from receipts
# Uncomment below lines if you want to create a new analyzer.

# CUSTOM_ANALYZER_ID = "invoice-extraction-demo"
# response = client.begin_create_analyzer(CUSTOM_ANALYZER_ID, analyzer_template_path=analyzer_template_path)
# result = client.poll_result(response)

# print(json.dumps(result, indent=2))

# response = client.begin_analyze(CUSTOM_ANALYZER_ID, file_location=analyzer_sample_file_path)
# result_json = client.poll_result(response)

def get_extracted_content(analyzer_id = "invoice-extraction-demo", file_location = "./data/invoice.png"):
    response = client.begin_analyze(analyzer_id, file_location=file_location)
    result_json = client.poll_result(response)
    extracted_result_json = result_json['result']['contents'][0]
    
    # print(json.dumps(extracted_result_json, indent=2))

    items = []
    if "fields" in extracted_result_json:
        extracted_fields = extracted_result_json['fields']
        for field_name, field_value in extracted_fields.items():
            if isinstance(field_value, dict) and 'valueString' in field_value:
                vendorName = field_value.get('valueString', '')
            elif isinstance(field_value, dict) and field_value['type'] == 'array':
                for  array in field_value['valueArray']:
                    items.append({"vendorName" : vendorName, "item_description" : array['valueObject']['Description']['valueString'], "amount" : array['valueObject']["Amount"]["valueNumber"]})
    return items

items = get_extracted_content(file_location="path/to/your/file.png")
print(json.dumps(items, indent=2))