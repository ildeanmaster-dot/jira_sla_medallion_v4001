"""
transform_jira.py (Silver)
Purpose:
- Read Bronze JSON and normalize nested structure into a slim CSV for SLA analysis.
- Clean/standardize columns and validate ISO datetime fields.

Output (Silver) columns (snake_case):
- issue_id
- issue_key
- created_at
- resolved_at
- status
- priority
- issue_type
- assignee_name

Date rules (compliance):
- If created_at is invalid -> drop the record.
- If resolved_at is invalid -> set to empty (keep until Gold, where Done/Resolved requires resolved_at).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _safe_get(obj: Any, path: List[Any]) -> Any:
    cur = obj
    for p in path:
        try:
            if isinstance(p, int) and isinstance(cur, list) and len(cur) > p:
                cur = cur[p]
            elif isinstance(p, str) and isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        except Exception:
            return None
    return cur


def _first_non_null(*values: Any) -> Any:
    for v in values:
        if v is not None and str(v).strip() != "":
            return v
    return None


def _parse_iso_utc(dt_str: str) -> Optional[str]:
    """
    Validate and normalize datetime string to ISO-8601 UTC with trailing 'Z'.
    Returns normalized string or None if invalid.
    """
    if dt_str is None:
        return None
    s = str(dt_str).strip()
    if s == "":
        return None

    # accept 'Z' or offset or naive; normalize to UTC
    try:
        if s.endswith("Z"):
            s2 = s[:-1]
            dt = datetime.fromisoformat(s2)
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _extract_issue_row(issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    issue_id = _first_non_null(_safe_get(issue, ["id"]), _safe_get(issue, ["issue_id"]))
    issue_key = _first_non_null(_safe_get(issue, ["key"]), _safe_get(issue, ["issue_key"]))

    status = _first_non_null(
        _safe_get(issue, ["status"]),
        _safe_get(issue, ["fields", "status", "name"]),
        _safe_get(issue, ["fields", "status"]),
    )

    priority = _first_non_null(
        _safe_get(issue, ["priority"]),
        _safe_get(issue, ["fields", "priority", "name"]),
        _safe_get(issue, ["fields", "priority"]),
    ) or "Low"

    issue_type = _first_non_null(
        _safe_get(issue, ["issue_type"]),
        _safe_get(issue, ["fields", "issuetype", "name"]),
        _safe_get(issue, ["fields", "issue_type"]),
    )

    assignee_name = _first_non_null(
        _safe_get(issue, ["assignee", "name"]),
        _safe_get(issue, ["assignee", "displayName"]),
        _safe_get(issue, ["fields", "assignee", "displayName"]),
        _safe_get(issue, ["fields", "assignee", "name"]),
        _safe_get(issue, ["assignee"]),
        _safe_get(issue, ["fields", "assignee"]),
        _safe_get(issue, ["assignee", 0, "name"]),
    )

    created_raw = _first_non_null(
        _safe_get(issue, ["timestamps", 0, "created_at"]),
        _safe_get(issue, ["created"]),
        _safe_get(issue, ["fields", "created"]),
    )
    resolved_raw = _first_non_null(
        _safe_get(issue, ["timestamps", 0, "resolved_at"]),
        _safe_get(issue, ["resolved"]),
        _safe_get(issue, ["fields", "resolutiondate"]),
        _safe_get(issue, ["fields", "resolved"]),
    )

    created_at = _parse_iso_utc(created_raw)
    if created_at is None:
        # compliance: drop records with invalid created_at
        return None

    resolved_at = _parse_iso_utc(resolved_raw) if resolved_raw else None
    # compliance: invalid resolved_at should become empty, not crash pipeline
    if resolved_raw and resolved_at is None:
        resolved_at = ""

    return {
        "issue_id": issue_id,
        "issue_key": issue_key,
        "created_at": created_at,
        "resolved_at": resolved_at or "",
        "status": (status or "").strip(),
        "priority": str(priority).strip(),
        "issue_type": (issue_type or "").strip(),
        "assignee_name": (assignee_name or "").strip(),
    }


def transform_jira(
    bronze_path: str = "data/bronze/bronze_jira.json",
    silver_path: str = "data/silver/silver_jira.csv",
) -> str:
    bronze_p = Path(bronze_path)
    if not bronze_p.exists():
        raise FileNotFoundError(f"Bronze file not found: {bronze_path}")

    with bronze_p.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict):
        issues = payload.get("issues", [])
    elif isinstance(payload, list):
        issues = payload
    else:
        raise ValueError("Bronze payload must be dict(with issues) or list.")

    rows: List[Dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        row = _extract_issue_row(issue)
        if row is not None:
            rows.append(row)

    df = pd.DataFrame(rows)

    expected_cols = [
        "issue_id",
        "issue_key",
        "created_at",
        "resolved_at",
        "status",
        "priority",
        "issue_type",
        "assignee_name",
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = ""

    df = df[expected_cols]

    silver_p = Path(silver_path)
    silver_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(silver_p, index=False)

    print(f"[SILVER] Rows: {len(df)}")
    print(f"[SILVER] Generated: {silver_p}")
    return str(silver_p)


if __name__ == "__main__":
    transform_jira()