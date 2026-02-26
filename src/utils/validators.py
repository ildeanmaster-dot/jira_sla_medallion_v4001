"""
validators.py
Objective:
- Automatic validations per layer (Bronze, Silver, Gold).
- Fail-fast: raise ValueError with a clear message if something is wrong.

Usage:
- Scripts in scripts/validate_*.py call these functions.
- run_pipeline.ps1 invokes the validate_*.py files at the end of each step.

Why this matters:
- Surface errors early (e.g. wrong schema in Silver).
- Prevent a "green pipeline" producing bad data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd


SILVER_REQUIRED_COLS: List[str] = [
    "issue_id",
    "issue_key",
    "created",
    "resolved",
    "status",
    "priority",
    "issue_type",
    "assignee",
]

GOLD_REQUIRED_COLS: List[str] = [
    "issue_id",
    "issue_key",
    "created",
    "resolved",
    "status",
    "priority",
    "issue_type",
    "assignee",
    "actual_hours",
    "sla_expected_hours",
    "is_sla_met",
]


def validate_bronze(bronze_path: str) -> None:
    """
    Bronze:
    - File must exist
    - Must be valid JSON
    - Should be either:
        - dict with key "issues" (list), OR
        - direct list
    """
    p = Path(bronze_path)
    if not p.exists():
        raise ValueError(f"Bronze file not found: {bronze_path}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Bronze JSON parse error: {e}") from e

    if isinstance(data, dict):
        issues = data.get("issues", None)
        if issues is None:
            raise ValueError("Bronze JSON is dict but missing key 'issues'.")
        if not isinstance(issues, list):
            raise ValueError("Bronze JSON 'issues' must be a list.")
        return

    if isinstance(data, list):
        return

    raise ValueError("Bronze JSON must be a dict (with issues) or a list.")


def validate_silver(silver_path: str) -> None:
    """
    Silver:
    - File must exist
    - Must contain required columns
    - created cannot be null (mandatory field)
    - issue_id should not have duplicates (when filled)
    """
    p = Path(silver_path)
    if not p.exists():
        raise ValueError(f"Silver file not found: {silver_path}")

    df = pd.read_csv(p)

    missing = [c for c in SILVER_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Silver missing required columns: {missing}")

    if df.shape[0] < 0:
        raise ValueError("Silver has invalid row count.")

    if df["created"].isna().any():
        raise ValueError("Silver has null created values (created is mandatory).")

    if df["issue_id"].notna().any():
        dup = df[df["issue_id"].duplicated(keep=False)]
        if not dup.empty:
            raise ValueError("Silver has duplicated issue_id values.")


def validate_gold(
    gold_path: str,
    report_by_analyst_path: str,
    report_by_type_path: str,
) -> None:
    """
    Gold:
    - File must exist
    - Must contain required columns
    - Should only contain status Done/Resolved
    - actual_hours >= 0
    - Reports must exist
    """
    gold_p = Path(gold_path)
    if not gold_p.exists():
        raise ValueError(f"Gold file not found: {gold_path}")

    df = pd.read_csv(gold_p)

    missing = [c for c in GOLD_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Gold missing required columns: {missing}")

    allowed = {"Done", "Resolved"}
    if not df["status"].isin(allowed).all():
        raise ValueError("Gold contains status other than Done/Resolved.")

    if (df["actual_hours"] < 0).any():
        raise ValueError("Gold contains negative actual_hours.")

    if df["is_sla_met"].isna().any():
        raise ValueError("Gold has null is_sla_met values.")

    r1 = Path(report_by_analyst_path)
    r2 = Path(report_by_type_path)

    if not r1.exists():
        raise ValueError(f"Gold report not found: {report_by_analyst_path}")

    if not r2.exists():
        raise ValueError(f"Gold report not found: {report_by_type_path}")