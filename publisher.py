import os
import re
import sys
import time
import shutil
import zipfile
import tempfile
import mimetypes
import argparse
from typing import Dict, List, Optional, Any

from azure.identity import ClientSecretCredential
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.storage.models import (
    StorageAccountCreateParameters,
    Sku,
    SkuName,
    Kind,
    StorageAccountPropertiesCreateParameters
)
from azure.storage.blob import BlobServiceClient, ContentSettings, StaticWebsite
from azure.core.exceptions import ResourceExistsError

import config


class AzureStaticPublisher:
    """
    Automated engine to provision and manage static website hosting on Azure Storage accounts.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id or config.AZURE_TENANT_ID
        self.client_id = client_id or config.AZURE_CLIENT_ID
        self.client_secret = client_secret or config.AZURE_CLIENT_SECRET
        self.subscription_id = subscription_id or config.AZURE_SUBSCRIPTION_ID

        if not all([self.tenant_id, self.client_id, self.client_secret, self.subscription_id]):
            raise ValueError(
                "Missing required Azure credentials. Ensure AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                "AZURE_CLIENT_SECRET, and AZURE_SUBSCRIPTION_ID are configured in environment or passed directly."
            )

        self.credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        self.storage_client = StorageManagementClient(self.credential, self.subscription_id)

    @staticmethod
    def sanitize_account_name(name: str) -> str:
        """Azure Storage account names must be between 3 and 24 characters and contain only lowercase letters and numbers."""
        clean = re.sub(r"[^a-z0-9]", "", name.lower())
        if len(clean) < 3:
            clean = f"site{clean}"
        return clean[:24]

    def ensure_resource_group(self, resource_group: str, location: str) -> str:
        """Ensures that the target Resource Group exists in the specified location."""
        try:
            rg = self.resource_client.resource_groups.get(resource_group)
            return rg.location
        except Exception:
            self.resource_client.resource_groups.create_or_update(
                resource_group, {"location": location}
            )
            return location

    def create_storage_account(
        self,
        account_name: str,
        resource_group: str,
        location: str
    ) -> str:
        """Provisions a standard StorageV2 account with public blob access."""
        clean_name = self.sanitize_account_name(account_name)
        self.ensure_resource_group(resource_group, location)

        params = StorageAccountCreateParameters(
            sku=Sku(name=SkuName.STANDARD_LRS),
            kind=Kind.STORAGE_V2,
            location=location,
            properties=StorageAccountPropertiesCreateParameters(allow_blob_public_access=True),
        )
        poller = self.storage_client.storage_accounts.begin_create(resource_group, clean_name, params)
        poller.result()
        return clean_name

    def fetch_primary_key(self, resource_group: str, account_name: str) -> str:
        """Retrieves the primary access key for the storage account."""
        keys_result = self.storage_client.storage_accounts.list_keys(resource_group, account_name)
        if hasattr(keys_result, "keys_property"):
            key_list = keys_result.keys_property
        elif hasattr(keys_result, "items"):
            key_list = dict(keys_result).get("keys", [])
        else:
            key_list = getattr(keys_result, "keys", [])

        if not key_list:
            raise RuntimeError(f"Could not retrieve access keys for storage account '{account_name}'.")

        first_key = key_list[0]
        return getattr(first_key, "value", first_key.get("value") if isinstance(first_key, dict) else "")

    def enable_static_website(
        self,
        account_name: str,
        resource_group: str,
        index_document: str = "index.html",
        error_document: str = "404.html"
    ) -> str:
        """Enables the $web container on the storage account and returns the public HTTP endpoint."""
        key = self.fetch_primary_key(resource_group, account_name)
        blob_svc = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=key
        )
        blob_svc.set_service_properties(
            static_website=StaticWebsite(
                enabled=True,
                index_document=index_document,
                error_document404_path=error_document
            )
        )

        # Poll for web endpoint availability
        web_endpoint = ""
        for _ in range(8):
            props = self.storage_client.storage_accounts.get_properties(resource_group, account_name)
            if props.primary_endpoints and props.primary_endpoints.web:
                web_endpoint = props.primary_endpoints.web.rstrip("/") + "/"
                break
            time.sleep(2)

        if not web_endpoint:
            web_endpoint = f"https://{account_name}.z13.web.core.windows.net/"

        return web_endpoint

    def upload_directory(
        self,
        account_name: str,
        resource_group: str,
        source_dir: str
    ) -> int:
        """Recursively uploads all files from a directory into the $web container with correct MIME types."""
        key = self.fetch_primary_key(resource_group, account_name)
        blob_svc = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=key
        )
        container_client = blob_svc.get_container_client("$web")
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass

        uploaded_count = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, source_dir).replace("\\", "/")
                content_type, _ = mimetypes.guess_type(rel_path)
                content_type = content_type or "application/octet-stream"

                with open(abs_path, "rb") as f:
                    blob_client = container_client.get_blob_client(rel_path)
                    blob_client.upload_blob(
                        f,
                        overwrite=True,
                        content_settings=ContentSettings(content_type=content_type)
                    )
                uploaded_count += 1

        return uploaded_count

    def deploy_site(
        self,
        account_name: str,
        source_path: str,
        resource_group: Optional[str] = None,
        location: Optional[str] = None,
        index_document: str = "index.html",
        error_document: str = "404.html"
    ) -> Dict[str, Any]:
        """High-level deployment handler for a directory or zip archive."""
        rg = resource_group or config.AZURE_RESOURCE_GROUP
        loc = location or config.AZURE_DEFAULT_LOCATION
        clean_name = self.sanitize_account_name(account_name)

        print(f"[*] Provisioning storage account '{clean_name}' in resource group '{rg}' ({loc})...")
        self.create_storage_account(clean_name, rg, loc)

        print(f"[*] Enabling static website hosting...")
        endpoint = self.enable_static_website(clean_name, rg, index_document, error_document)

        print(f"[*] Uploading website assets from '{source_path}'...")
        if os.path.isfile(source_path) and zipfile.is_zipfile(source_path):
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(source_path, "r") as z:
                    z.extractall(tmp_dir)
                file_count = self.upload_directory(clean_name, rg, tmp_dir)
        elif os.path.isdir(source_path):
            file_count = self.upload_directory(clean_name, rg, source_path)
        else:
            raise FileNotFoundError(f"Source path '{source_path}' is neither a directory nor a valid zip file.")

        print(f"[+] Successfully deployed {file_count} files!")
        print(f"[+] Live Web Endpoint: {endpoint}")

        return {
            "account_name": clean_name,
            "resource_group": rg,
            "location": loc,
            "web_endpoint": endpoint,
            "files_uploaded": file_count
        }

    def list_sites(self, resource_group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all storage accounts in the resource group with their static web endpoints."""
        rg = resource_group or config.AZURE_RESOURCE_GROUP
        sites = []
        try:
            accounts = self.storage_client.storage_accounts.list_by_resource_group(rg)
            for acct in accounts:
                web_endpoint = getattr(acct.primary_endpoints, "web", None) if acct.primary_endpoints else None
                sites.append({
                    "name": acct.name,
                    "location": acct.location,
                    "resource_group": rg,
                    "web_endpoint": web_endpoint,
                    "status": "Active" if web_endpoint else "Storage Only",
                    "creation_time": acct.creation_time.isoformat() if acct.creation_time else None
                })
        except Exception as e:
            print(f"[!] Error listing storage accounts in {rg}: {e}")
        return sites

    def delete_site(self, account_name: str, resource_group: Optional[str] = None) -> bool:
        """Deletes a storage account to stop cloud billing."""
        rg = resource_group or config.AZURE_RESOURCE_GROUP
        try:
            print(f"[*] Deleting storage account '{account_name}' from '{rg}'...")
            self.storage_client.storage_accounts.delete(rg, account_name)
            print(f"[+] Storage account '{account_name}' deleted successfully.")
            return True
        except Exception as e:
            print(f"[!] Failed to delete storage account '{account_name}': {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Azure Static Site Publisher - Deploy & manage static websites on Azure Storage"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Deploy subcommand
    deploy_parser = subparsers.add_parser("deploy", help="Deploy static site from folder or zip")
    deploy_parser.add_argument("name", help="Name for the Azure storage account (alphanumeric, 3-24 chars)")
    deploy_parser.add_argument("source", help="Path to static website directory or .zip archive")
    deploy_parser.add_argument("-g", "--resource-group", help="Target Azure resource group", default=None)
    deploy_parser.add_argument("-l", "--location", help="Target Azure region", default=None)
    deploy_parser.add_argument("--index", help="Index document name", default="index.html")
    deploy_parser.add_argument("--error", help="404 error document name", default="404.html")

    # List subcommand
    list_parser = subparsers.add_parser("list", help="List all deployed static sites in resource group")
    list_parser.add_argument("-g", "--resource-group", help="Resource group to query", default=None)

    # Delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Teardown and delete a deployed storage account")
    delete_parser.add_argument("name", help="Storage account name to delete")
    delete_parser.add_argument("-g", "--resource-group", help="Resource group containing the account", default=None)
    delete_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    try:
        publisher = AzureStaticPublisher()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if args.command == "deploy":
        publisher.deploy_site(
            account_name=args.name,
            source_path=args.source,
            resource_group=args.resource_group,
            location=args.location,
            index_document=args.index,
            error_document=args.error
        )
    elif args.command == "list":
        sites = publisher.list_sites(resource_group=args.resource_group)
        if not sites:
            print("No sites found.")
            return
        print(f"\n{'NAME':<24} {'LOCATION':<16} {'STATUS':<12} {'WEB ENDPOINT'}")
        print("-" * 80)
        for s in sites:
            endpoint = s["web_endpoint"] or "N/A"
            print(f"{s['name']:<24} {s['location']:<16} {s['status']:<12} {endpoint}")
    elif args.command == "delete":
        if not args.yes:
            confirm = input(f"Are you sure you want to permanently delete '{args.name}'? (y/N): ")
            if confirm.lower() != "y":
                print("Aborted.")
                return
        publisher.delete_site(account_name=args.name, resource_group=args.resource_group)


if __name__ == "__main__":
    main()
