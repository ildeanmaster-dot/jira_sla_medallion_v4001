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
    """
    Defensive navigation through nested dict/list structures.
    Returns None if the path cannot be resolved.
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
    """
    Return the first value that is not None and not empty after string conversion.
    """
    for v in values:
        if v is None:
            continue
        if isinstance(v, str):
            if v.strip() != "":
                return v
        else:
            # for non-strings, accept as-is if not "empty-like"
            if str(v).strip() != "":
                return v
    return None


def _parse_iso_utc(dt_str: Any) -> Optional[str]:
    """
    Validate and normalize datetime string to ISO-8601 UTC with trailing 'Z'.
    Accepts:
    - '...Z'
    - ISO with timezone offset
    - naive ISO (assumed UTC)
    Returns normalized string or None if invalid.
    """
    if dt_str is None:
        return None

    s = str(dt_str).strip()
    if s == "":
        return None

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

        # normalize: drop microseconds and enforce Z suffix
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    except Exception:
        return None


def _coerce_text(value: Any) -> str:
    """
    Normalize a field that may come as:
    - str
    - dict (common keys: name, displayName, value, id)
    - list (take first element)
    into a safe string.
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        v = (
            value.get("displayName")
            or value.get("name")
            or value.get("value")
            or value.get("label")
            or value.get("id")
        )
        return str(v).strip() if v is not None else ""

    if isinstance(value, list):
        if len(value) == 0:
            return ""
        return _coerce_text(value[0])

    return str(value).strip()


def _coerce_assignee_name(value: Any) -> str:
    """
    Normalize assignee into a safe string.
    Supported inputs:
    - str
    - dict (displayName/name/email/emailAddress)
    - list of dicts/strings (take first)
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        v = (
            value.get("displayName")
            or value.get("name")
            or value.get("email")
            or value.get("emailAddress")
        )
        return str(v).strip() if v else ""

    if isinstance(value, list):
        if len(value) == 0:
            return ""
        return _coerce_assignee_name(value[0])

    return str(value).strip()


def _extract_issue_row(issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract one normalized row from a single issue dict.
    Returns None if created_at is invalid (compliance rule).
    """
    issue_id = _first_non_null(
        _safe_get(issue, ["id"]),
        _safe_get(issue, ["issue_id"]),
    )

    issue_key = _first_non_null(
        _safe_get(issue, ["key"]),
        _safe_get(issue, ["issue_key"]),
    )

    # status/priority/type can arrive as strings, dicts, or even lists in some payloads
    status_raw = _first_non_null(
        _safe_get(issue, ["status"]),
        _safe_get(issue, ["fields", "status", "name"]),
        _safe_get(issue, ["fields", "status"]),
    )
    priority_raw = _first_non_null(
        _safe_get(issue, ["priority"]),
        _safe_get(issue, ["fields", "priority", "name"]),
        _safe_get(issue, ["fields", "priority"]),
    )
    issue_type_raw = _first_non_null(
        _safe_get(issue, ["issue_type"]),
        _safe_get(issue, ["fields", "issuetype", "name"]),
        _safe_get(issue, ["fields", "issue_type"]),
    )

    status = _coerce_text(status_raw)
    priority = _coerce_text(priority_raw) or "Low"
    issue_type = _coerce_text(issue_type_raw)

    # Assignee can be str/dict/list depending on source schema
    assignee_raw = _first_non_null(
        _safe_get(issue, ["assignee", "displayName"]),
        _safe_get(issue, ["assignee", "name"]),
        _safe_get(issue, ["assignee", "email"]),
        _safe_get(issue, ["fields", "assignee", "displayName"]),
        _safe_get(issue, ["fields", "assignee", "name"]),
        _safe_get(issue, ["fields", "assignee", "emailAddress"]),
        _safe_get(issue, ["assignee"]),            # might be dict/list/string
        _safe_get(issue, ["fields", "assignee"]),  # might be dict
        _safe_get(issue, ["assignee", 0]),         # list case
        _safe_get(issue, ["assignee", 0, "name"]),
        _safe_get(issue, ["assignee", 0, "email"]),
    )
    assignee_name = _coerce_assignee_name(assignee_raw)

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

    resolved_at: str = ""
    if resolved_raw:
        parsed_resolved = _parse_iso_utc(resolved_raw)
        # compliance: invalid resolved_at becomes empty (keeps record until Gold)
        resolved_at = parsed_resolved if parsed_resolved is not None else ""

    return {
        "issue_id": issue_id,
        "issue_key": issue_key,
        "created_at": created_at,
        "resolved_at": resolved_at,
        "status": status,
        "priority": priority,
        "issue_type": issue_type,
        "assignee_name": assignee_name,
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