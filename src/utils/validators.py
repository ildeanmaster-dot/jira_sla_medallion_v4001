"""
validators.py
Centralized validations for Bronze/Silver/Gold artifacts.
Fail-fast with clear messages.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd


def _fail(msg: str) -> None:
    raise ValueError(msg)


def validate_bronze(bronze_path: str) -> None:
    p = Path(bronze_path)
    if not p.exists():
        _fail(f"[BRONZE] File not found: {bronze_path}")
    if p.stat().st_size <= 0:
        _fail(f"[BRONZE] File is empty: {bronze_path}")

    try:
        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        _fail(f"[BRONZE] Invalid JSON: {e}")

    if not isinstance(payload, (dict, list)):
        _fail("[BRONZE] Payload must be dict or list")

    # Soft check: if dict, 'issues' is expected (not mandatory)
    if isinstance(payload, dict) and "issues" in payload and not isinstance(payload["issues"], list):
        _fail("[BRONZE] 'issues' must be a list when present")


def _require_cols(df: pd.DataFrame, cols: List[str], ctx: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        _fail(f"[{ctx}] Missing columns: {missing}")


def validate_silver(silver_path: str) -> None:
    p = Path(silver_path)
    if not p.exists():
        _fail(f"[SILVER] File not found: {silver_path}")
    if p.stat().st_size <= 0:
        _fail(f"[SILVER] File is empty: {silver_path}")

    df = pd.read_csv(p)

    required = [
        "issue_id",
        "issue_key",
        "created_at",
        "resolved_at",
        "status",
        "priority",
        "issue_type",
        "assignee_name",
    ]
    _require_cols(df, required, "SILVER")

    # Basic content checks
    if df["created_at"].isna().any():
        _fail("[SILVER] created_at contains nulls (should be dropped in transform)")
    if (df["created_at"].astype(str).str.strip() == "").any():
        _fail("[SILVER] created_at contains empty strings (should be dropped in transform)")


def validate_gold(
    gold_path: str,
    report_by_analyst_path: str,
    report_by_type_path: str,
) -> None:
    gp = Path(gold_path)
    if not gp.exists():
        _fail(f"[GOLD] File not found: {gold_path}")

    gdf = pd.read_csv(gp)

    required_gold = [
        "issue_id",
        "issue_type",
        "assignee_name",
        "priority",
        "created_at",
        "resolved_at",
        "resolution_hours",
        "sla_expected_hours",
        "is_sla_met",
    ]
    _require_cols(gdf, required_gold, "GOLD")

    rap = Path(report_by_analyst_path)
    if not rap.exists():
        _fail(f"[GOLD-REPORT] File not found: {report_by_analyst_path}")
    rdf_a = pd.read_csv(rap)
    _require_cols(rdf_a, ["assignee_name", "count_issues", "avg_resolution_hours"], "GOLD-REPORT-ANALYST")

    rtp = Path(report_by_type_path)
    if not rtp.exists():
        _fail(f"[GOLD-REPORT] File not found: {report_by_type_path}")
    rdf_t = pd.read_csv(rtp)
    _require_cols(rdf_t, ["issue_type", "count_issues", "avg_resolution_hours"], "GOLD-REPORT-TYPE")