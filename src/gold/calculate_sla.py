"""
calculate_sla.py (Gold)
Purpose:
- Apply business rules and compute SLA metrics.
- Use dedicated SLA module (sla_calculation.py).
- Output standardized column names per convention.

Gold output columns (minimum required):
- issue_id
- issue_type
- assignee_name
- priority
- created_at
- resolved_at
- resolution_hours
- sla_expected_hours
- is_sla_met

Reports (required):
- SLA avg by analyst: assignee_name, count_issues, avg_resolution_hours
- SLA avg by issue type: issue_type, count_issues, avg_resolution_hours
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.sla_calculation import (
    calculate_resolution_hours,
    get_expected_sla_hours,
    is_sla_met,
)


def calculate_sla(
    silver_path: str = "data/silver/silver_jira.csv",
    gold_path: str = "data/gold/gold_jira_sla.csv",
    report_by_analyst_path: str = "data/gold/gold_sla_by_analyst.csv",
    report_by_type_path: str = "data/gold/gold_sla_by_issue_type.csv",
) -> str:
    silver_p = Path(silver_path)
    if not silver_p.exists():
        raise FileNotFoundError(f"Silver file not found: {silver_path}")

    df = pd.read_csv(silver_p)

    required = [
        "issue_id",
        "created_at",
        "resolved_at",
        "status",
        "priority",
        "issue_type",
        "assignee_name",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Silver missing required columns: {missing}")

    # Keep only Done/Resolved with resolved_at filled
    df["status"] = df["status"].astype(str).str.strip()
    df["resolved_at"] = df["resolved_at"].astype(str).str.strip()

    df = df[df["status"].isin(["Done", "Resolved"])].copy()
    df = df[df["resolved_at"].notna() & (df["resolved_at"] != "")].copy()

    gold_p = Path(gold_path)
    gold_p.parent.mkdir(parents=True, exist_ok=True)

    if df.empty:
        out = pd.DataFrame(
            columns=[
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
        )
        out.to_csv(gold_p, index=False)

        # Empty reports
        Path(report_by_analyst_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["assignee_name", "count_issues", "avg_resolution_hours"]).to_csv(
            report_by_analyst_path, index=False
        )
        pd.DataFrame(columns=["issue_type", "count_issues", "avg_resolution_hours"]).to_csv(
            report_by_type_path, index=False
        )

        print("[GOLD] No Done/Resolved rows with resolved_at. Generated empty outputs.")
        return str(gold_p)

    # Compute metrics
    df["resolution_hours"] = df.apply(
        lambda r: calculate_resolution_hours(str(r["created_at"]), str(r["resolved_at"])),
        axis=1,
    )
    df["sla_expected_hours"] = df["priority"].apply(get_expected_sla_hours)
    df["is_sla_met"] = df.apply(
        lambda r: is_sla_met(float(r["resolution_hours"]), float(r["sla_expected_hours"])),
        axis=1,
    )

    gold_df = df[
        [
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
    ].copy()

    gold_df.to_csv(gold_p, index=False)

    # Reports with count_issues + avg_resolution_hours
    by_analyst = (
        gold_df.groupby("assignee_name", dropna=False)
        .agg(
            count_issues=("issue_id", "count"),
            avg_resolution_hours=("resolution_hours", "mean"),
        )
        .reset_index()
    )
    by_analyst["avg_resolution_hours"] = by_analyst["avg_resolution_hours"].round(2)
    by_analyst.to_csv(report_by_analyst_path, index=False)

    by_type = (
        gold_df.groupby("issue_type", dropna=False)
        .agg(
            count_issues=("issue_id", "count"),
            avg_resolution_hours=("resolution_hours", "mean"),
        )
        .reset_index()
    )
    by_type["avg_resolution_hours"] = by_type["avg_resolution_hours"].round(2)
    by_type.to_csv(report_by_type_path, index=False)

    # Compatibility file (optional but useful): also write gold_sla_by_type.csv
    compat_path = Path("data/gold/gold_sla_by_type.csv")
    by_type.to_csv(compat_path, index=False)

    print(f"[GOLD] Rows: {len(gold_df)}")
    print(f"[GOLD] Generated: {gold_p}")
    print(f"[GOLD] Report analyst: {report_by_analyst_path}")
    print(f"[GOLD] Report type:    {report_by_type_path}")
    print(f"[GOLD] Report type2:   {compat_path}")

    return str(gold_p)


if __name__ == "__main__":
    calculate_sla()