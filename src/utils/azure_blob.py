"""
azure_blob.py
Objective:
- Download raw JSON from Azure Blob Storage (read-only) using a Service Principal.
- Automatically fall back to local JSON at data/raw/jira_issues_raw.json on failure.
- Also return the data source (AZURE_BLOB or LOCAL_FALLBACK) for auditing.

Returns:
- tuple(payload: dict, source: str)

source:
- "AZURE_BLOB"       -> successfully downloaded from Azure
- "LOCAL_FALLBACK"   -> read from local file (due to missing config or network/ssl/permission issue)

Env vars (.env):
- AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
- AZURE_STORAGE_ACCOUNT (name OR full host)
- AZURE_STORAGE_CONTAINER
- AZURE_STORAGE_BLOB (optional; default jira_issues_raw.json)
- AZURE_CA_BUNDLE (optional; e.g. C:\\Certs\\corp-root-ca.pem)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from azure.core.pipeline.transport import RequestsTransport


def _read_local_fallback(local_path: Path) -> Dict[str, Any]:
    if not local_path.exists():
        return {"issues": []}
    with local_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_storage_account(account_value: str) -> str:
    s = str(account_value).strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    s = s.replace(".blob.core.windows.net", "")
    s = s.strip("/")
    return s


def download_blob_json(
    local_fallback_path: str = "data/raw/jira_issues_raw.json",
) -> Tuple[Dict[str, Any], str]:
    """
    Returns (payload, source).
    """
    load_dotenv()

    local_path = Path(local_fallback_path)

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER")
    blob_name = os.getenv("AZURE_STORAGE_BLOB", "jira_issues_raw.json")

    # If config is missing, don't even try Azure
    if not all([tenant_id, client_id, client_secret, account, container]):
        return _read_local_fallback(local_path), "LOCAL_FALLBACK"

    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        account_name = _normalize_storage_account(account)
        account_url = f"https://{account_name}.blob.core.windows.net"

        ca_bundle = os.getenv("AZURE_CA_BUNDLE")
        verify_value: object = True

        # If a custom CA bundle is provided, validate its existence and use it
        if ca_bundle and ca_bundle.strip():
            ca_path = ca_bundle.strip()
            if not os.path.exists(ca_path):
                return _read_local_fallback(local_path), "LOCAL_FALLBACK"
            verify_value = ca_path

        transport = RequestsTransport(connection_verify=verify_value)

        bsc = BlobServiceClient(
            account_url=account_url,
            credential=credential,
            transport=transport,
        )

        blob_client = bsc.get_blob_client(container=container, blob=blob_name)
        raw_bytes = blob_client.download_blob().readall()

        payload = json.loads(raw_bytes.decode("utf-8"))
        return payload, "AZURE_BLOB"

    except Exception:
        return _read_local_fallback(local_path), "LOCAL_FALLBACK"