"""
azure_blob.py
Objetivo:
- Baixar JSON bruto do Azure Blob Storage (somente leitura) usando Service Principal.
- Carregar variaveis via dotenv (.env).
- Fazer fallback automatico para JSON local em data/raw/jira_issues_raw.json em caso de falha.

Cenarios suportados:
1) Execucao local sem Azure (offline):
   - Se faltar variavel de ambiente, le o JSON local (fallback) e segue o pipeline.

2) Execucao com Azure:
   - Autentica via AAD (ClientSecretCredential)
   - Conecta no Blob e baixa o JSON

3) Ambiente corporativo com inspecao TLS (proxy):
   - Se a rede injeta certificado (self-signed na cadeia), voce precisa confiar no CA raiz corporativo.
   - Para isso, defina AZURE_CA_BUNDLE no .env apontando para um .pem/.crt valido.
   - O transporte RequestsTransport vai usar esse CA para validar SSL.

Variaveis esperadas (.env):
- AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
- AZURE_STORAGE_ACCOUNT (nome OU host completo)
- AZURE_STORAGE_CONTAINER
- AZURE_STORAGE_BLOB (opcional; default jira_issues_raw.json)
- AZURE_CA_BUNDLE (opcional; ex: C:\\Certs\\corp-root-ca.pem)

Seguranca:
- Nao versionar .env (mantido no .gitignore)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from azure.core.pipeline.transport import RequestsTransport


def _read_local_fallback(local_path: Path) -> Dict[str, Any]:
    """
    Le o JSON local de fallback.
    Se nao existir, retorna estrutura minima valida.
    """
    if not local_path.exists():
        return {"issues": []}

    with local_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_storage_account(account_value: str) -> str:
    """
    Aceita:
    - stfasttracksdev
    - stfasttracksdev.blob.core.windows.net
    - https://stfasttracksdev.blob.core.windows.net

    Retorna:
    - stfasttracksdev
    """
    s = str(account_value).strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    s = s.replace(".blob.core.windows.net", "")
    s = s.strip("/")
    return s


def download_blob_json(
    local_fallback_path: str = "data/raw/jira_issues_raw.json",
) -> Dict[str, Any]:
    """
    Tenta baixar JSON do Azure Blob.
    Se falhar por qualquer motivo (rede, proxy, permissao, credencial),
    retorna JSON local (fallback).
    """
    load_dotenv()

    local_path = Path(local_fallback_path)

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER")
    blob_name = os.getenv("AZURE_STORAGE_BLOB", "jira_issues_raw.json")

    # Se faltou config, nao tenta Azure
    if not all([tenant_id, client_id, client_secret, account, container]):
        return _read_local_fallback(local_path)

    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        account_name = _normalize_storage_account(account)
        account_url = f"https://{account_name}.blob.core.windows.net"

        # Suporte a CA corporativo para SSL (proxy TLS)
        ca_bundle = os.getenv("AZURE_CA_BUNDLE")
        verify_value: object = True

        if ca_bundle and ca_bundle.strip():
            ca_path = ca_bundle.strip()
            if not os.path.exists(ca_path):
                # Se CA bundle foi informado mas nao existe, melhor falhar para cair no fallback
                return _read_local_fallback(local_path)

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
        return payload

    except Exception:
        # Fallback resiliente (offline / credencial / proxy / permissao / rede)
        return _read_local_fallback(local_path)