import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
AZURE_RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "rg-static-sites")
AZURE_DEFAULT_LOCATION = os.environ.get("AZURE_DEFAULT_LOCATION", "eastus")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-me")
PORT = int(os.environ.get("PORT", 5000))

# Supported Azure global regions for Static Websites
AZURE_REGIONS = {
    "eastus": "US East (Virginia)",
    "eastus2": "US East 2 (Virginia)",
    "westus2": "US West 2 (Washington)",
    "centralus": "US Central (Iowa)",
    "westeurope": "Europe West (Netherlands)",
    "northeurope": "Europe North (Ireland)",
    "uksouth": "UK South (London)",
    "southeastasia": "Asia Pacific (Singapore)",
    "eastasia": "Asia Pacific (Hong Kong)",
    "australiaeast": "Australia East (New South Wales)",
    "centralindia": "India Central (Pune)",
    "japaneast": "Japan East (Tokyo)",
    "brazilsouth": "Brazil South (Sao Paulo State)",
}

def is_configured() -> bool:
    """Check if all required Azure credentials are set in environment."""
    return bool(
        AZURE_TENANT_ID and 
        AZURE_CLIENT_ID and 
        AZURE_CLIENT_SECRET and 
        AZURE_SUBSCRIPTION_ID
    )
