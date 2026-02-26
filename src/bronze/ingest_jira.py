"""
ingest_jira.py (Bronze)
Objective:
- Ingest raw JIRA JSON via Azure Blob (read-only) with local fallback.
- Persist faithful copy of payload to data/bronze/bronze_jira.json
- Persist evidence of source to data/bronze/bronze_jira_source.json

Generated files:
- data/bronze/bronze_jira.json
- data/bronze/bronze_jira_source.json  (source: AZURE_BLOB or LOCAL_FALLBACK)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.utils.azure_blob import download_blob_json


def ingest_jira_raw(
    output_path: str = "data/bronze/bronze_jira.json",
    source_path: str = "data/bronze/bronze_jira_source.json",
    local_fallback_path: str = "data/raw/jira_issues_raw.json",
) -> str:
    payload, source = download_blob_json(local_fallback_path=local_fallback_path)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Copia fiel do payload
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Evidencia de origem (sidecar)
    evidence = {
        "source": source,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "azure_storage_account": os.getenv("AZURE_STORAGE_ACCOUNT"),
        "azure_storage_container": os.getenv("AZURE_STORAGE_CONTAINER"),
        "azure_storage_blob": os.getenv("AZURE_STORAGE_BLOB", "jira_issues_raw.json"),
        "fallback_path": local_fallback_path,
    }

    sp = Path(source_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    with sp.open("w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(f"[BRONZE] Source: {source}")
    print(f"[BRONZE] Generated: {out}")
    print(f"[BRONZE] Evidence:  {sp}")

    return str(out)


if __name__ == "__main__":
    ingest_jira_raw()