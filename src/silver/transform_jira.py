"""
transform_jira.py (Silver)
Objective:
- Read Bronze JSON (faithful copy) and normalize into a "lean" CSV table focused on SLA.

Output contract (columns):
- issue_id
- issue_key
- created
- resolved
- status
- priority
- issue_type
- assignee

Rules:
- Silver does cleaning/normalization but DOES NOT apply SLA business rules (that is Gold).
- Should be robust for nested JSON and missing fields.
- created is mandatory: records without created should be ignored.
- Keep Open/In progress items (Gold filters later).

Supported Bronze input:
- dict with key "issues" (list)
- or direct list of issues

Note:
- Avoid pd.read_json to prevent schema surprises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _safe_get(obj: Any, path: List[Any]) -> Any:
    """
    Safely access a path in a dict/list structure.
    path may contain keys (str) and indices (int).
    Returns None if navigation fails.
    """
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


def _extract_issue_row(issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract a normalized row from a single issue.
    Returns None if created is invalid/missing.
    """
    issue_id = _first_non_null(
        _safe_get(issue, ["id"]),
        _safe_get(issue, ["issue_id"]),
    )

    issue_key = _first_non_null(
        _safe_get(issue, ["key"]),
        _safe_get(issue, ["issue_key"]),
    )

    status = _first_non_null(
        _safe_get(issue, ["status"]),
        _safe_get(issue, ["fields", "status", "name"]),
        _safe_get(issue, ["fields", "status"]),
    )

    priority = _first_non_null(
        _safe_get(issue, ["priority"]),
        _safe_get(issue, ["fields", "priority", "name"]),
        _safe_get(issue, ["fields", "priority"]),
    )

    issue_type = _first_non_null(
        _safe_get(issue, ["issue_type"]),
        _safe_get(issue, ["fields", "issuetype", "name"]),
        _safe_get(issue, ["fields", "issue_type"]),
    )

    # Assignee may come as dict, string, or list (in custom schema)
    assignee_name = _first_non_null(
        _safe_get(issue, ["assignee", "name"]),
        _safe_get(issue, ["assignee", "displayName"]),
        _safe_get(issue, ["fields", "assignee", "displayName"]),
        _safe_get(issue, ["fields", "assignee", "name"]),
        _safe_get(issue, ["assignee"]),
        _safe_get(issue, ["fields", "assignee"]),
        _safe_get(issue, ["assignee", 0, "name"]),
        _safe_get(issue, ["assignee", 0, "email"]),
    )

    # Timestamps (custom schema of the challenge): timestamps[0].created_at / resolved_at
    created = _first_non_null(
        _safe_get(issue, ["timestamps", 0, "created_at"]),
        _safe_get(issue, ["created"]),
        _safe_get(issue, ["fields", "created"]),
    )

    resolved = _first_non_null(
        _safe_get(issue, ["timestamps", 0, "resolved_at"]),
        _safe_get(issue, ["resolved"]),
        _safe_get(issue, ["fields", "resolutiondate"]),
        _safe_get(issue, ["fields", "resolved"]),
    )

    # created is mandatory for SLA
    if created is None:
        return None

    row = {
        "issue_id": issue_id,
        "issue_key": issue_key,
        "created": created,
        "resolved": resolved,
        "status": status,
        "priority": (priority or "Low"),
        "issue_type": issue_type,
        "assignee": assignee_name,
    }

    return row


def transform_jira(
    bronze_path: str = "data/bronze/bronze_jira.json",
    silver_path: str = "data/silver/silver_jira.csv",
) -> str:
    """
    Execute the Silver transformation:
    - Read Bronze JSON
    - Extract normalized rows
    - Save Silver CSV
    """
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

    # Ensure expected columns exist (even if empty)
    expected_cols = [
        "issue_id",
        "issue_key",
        "created",
        "resolved",
        "status",
        "priority",
        "issue_type",
        "assignee",
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = None

    df = df[expected_cols]

    silver_p = Path(silver_path)
    silver_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(silver_p, index=False)

    print(f"[SILVER] Rows: {len(df)}")
    print(f"[SILVER] Generated: {silver_p}")
    return str(silver_p)


if __name__ == "__main__":
    transform_jira()