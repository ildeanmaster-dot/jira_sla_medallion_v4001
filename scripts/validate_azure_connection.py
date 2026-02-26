"""
validate_azure_connection.py
Objective:
- Validate connection to Azure Blob Storage using Service Principal (ClientSecretCredential)
- Validate environment variables (.env via dotenv)
- Validate AAD authentication (obtain token)
- Validate blob access (exists + partial download)

Usage:
  python .\scripts\validate_azure_connection.py

Outputs:
- Exit code 0: success
- Exit code 1: failure (clear message)
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient


def fail(msg: str) -> None:
    print(f"[AZURE-VALIDATION][ERROR] {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"[AZURE-VALIDATION][OK] {msg}")


def main() -> None:
    load_dotenv()

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER")
    blob_name = os.getenv("AZURE_STORAGE_BLOB", "jira_issues_raw.json")

    # =========================================================
    # Validacao 1: Variaveis obrigatorias presentes
    # =========================================================
    missing = []
    for k, v in [
        ("AZURE_TENANT_ID", tenant_id),
        ("AZURE_CLIENT_ID", client_id),
        ("AZURE_CLIENT_SECRET", client_secret),
        ("AZURE_STORAGE_ACCOUNT", account),
        ("AZURE_STORAGE_CONTAINER", container),
    ]:
        if v is None or str(v).strip() == "":
            missing.append(k)

    if missing:
        fail(f"Missing required env vars: {missing}. Check your .env file.")

    ok("Required environment variables are present.")

    # =========================================================
    # Validacao 2: Autenticacao AAD (token)
    # =========================================================
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Scope padrao do Storage
        token = credential.get_token("https://storage.azure.com/.default")
        if token is None or token.token is None or token.token.strip() == "":
            fail("AAD token acquisition returned empty token.")
    except Exception as e:
        fail(f"AAD authentication failed: {type(e).__name__}: {e}")

    ok("AAD authentication OK (token acquired).")

    # =========================================================
    # Validacao 3: Acesso ao Blob (exists + download parcial)
    # =========================================================
    try:
        account_url = f"https://{account}.blob.core.windows.net"
        bsc = BlobServiceClient(account_url=account_url, credential=credential)

        blob_client = bsc.get_blob_client(container=container, blob=blob_name)

        exists = blob_client.exists()
        if not exists:
            fail(f"Blob not found or no access: container='{container}', blob='{blob_name}'")

        # Download parcial: baixa os primeiros bytes para validar permissao de leitura
        stream = blob_client.download_blob(offset=0, length=1024)
        data = stream.readall()
        if data is None or len(data) == 0:
            fail("Blob download returned empty content (unexpected).")

    except Exception as e:
        fail(f"Blob access failed: {type(e).__name__}: {e}")

    ok(f"Blob access OK (exists + partial download). Container='{container}', Blob='{blob_name}'")
    ok("Azure connection validation completed successfully.")


if __name__ == "__main__":
    main()