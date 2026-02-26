"""
validate_bronze_source.py
Valida se o Bronze veio do Azure Blob ou do fallback local.
"""

from __future__ import annotations

import json
from pathlib import Path


def fail(msg: str) -> None:
    print(f"[VALIDATE-SOURCE][ERROR] {msg}")
    raise SystemExit(1)


def main() -> None:
    evidence_path = Path("data/bronze/bronze_jira_source.json")

    if not evidence_path.exists():
        fail("Evidence file not found. Run Bronze ingestion first.")

    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    source = data.get("source")

    if source not in {"AZURE_BLOB", "LOCAL_FALLBACK"}:
        fail(f"Invalid source value in evidence: {source}")

    print(f"[VALIDATE-SOURCE][OK] Bronze source = {source}")
    print(f"[VALIDATE-SOURCE][OK] Evidence file = {evidence_path}")


if __name__ == "__main__":
    main()