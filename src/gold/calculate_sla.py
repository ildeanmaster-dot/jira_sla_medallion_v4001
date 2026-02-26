"""
calculate_sla.py (Gold)
Objetivo:
- Ler Silver (CSV normalizado)
- Filtrar apenas issues Done/Resolved com resolved preenchido
- Calcular SLA em horas uteis (actual_hours)
- Mapear SLA esperado por prioridade:
    High   -> 24
    Medium -> 72
    Low    -> 120
- Gerar tabela Gold final:
    data/gold/gold_jira_sla.csv
- Gerar relatorios agregados:
    data/gold/gold_sla_by_analyst.csv
    data/gold/gold_sla_by_type.csv
    data/gold/gold_sla_by_issue_type.csv  (nome canonico + compat runner)

Observacoes:
- Gold e onde entram as regras de negocio (SLA e filtro Done/Resolved).
- Parsing defensivo e normalizacao minima de strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from src.utils.date_utils import calculate_business_hours


SLA_BY_PRIORITY: Dict[str, float] = {
    "high": 24.0,
    "medium": 72.0,
    "low": 120.0,
}


def _norm_str(x) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _norm_priority(p: str) -> str:
    s = _norm_str(p).lower()
    if s in {"highest", "high"}:
        return "high"
    if s in {"medium", "med"}:
        return "medium"
    if s in {"lowest", "low"}:
        return "low"
    # fallback padrao do desafio
    return "low"


def _to_float_hours(val) -> float:
    """
    Garante retorno escalar float, mesmo que venha algo estranho.
    """
    try:
        return float(val)
    except Exception:
        return 0.0


def calculate_sla(
    silver_path: str = "data/silver/silver_jira.csv",
    gold_path: str = "data/gold/gold_jira_sla.csv",
    report_by_analyst_path: str = "data/gold/gold_sla_by_analyst.csv",
    report_by_type_path: str = "data/gold/gold_sla_by_type.csv",
    report_by_issue_type_path: str = "data/gold/gold_sla_by_issue_type.csv",
) -> str:
    silver_p = Path(silver_path)
    if not silver_p.exists():
        raise FileNotFoundError(f"Silver file not found: {silver_path}")

    df = pd.read_csv(silver_p)

    # Validacao minima de colunas esperadas (contrato Silver)
    required = [
        "issue_id",
        "issue_key",
        "created",
        "resolved",
        "status",
        "priority",
        "issue_type",
        "assignee",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Silver missing required columns: {missing}")

    # Normalizacao defensiva
    df["status"] = df["status"].astype(str).str.strip()
    df["priority"] = df["priority"].astype(str).str.strip()
    df["issue_type"] = df["issue_type"].astype(str).str.strip()
    df["assignee"] = df["assignee"].astype(str).str.strip()

    # Filtro Gold: apenas Done/Resolved com resolved preenchido
    df = df[df["status"].isin(["Done", "Resolved"])].copy()
    df = df[df["resolved"].notna() & (df["resolved"].astype(str).str.strip() != "")].copy()

    if df.empty:
        # Ainda gera arquivos para pipeline nao quebrar, mas informa claramente
        out_p = Path(gold_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df_out = pd.DataFrame(columns=[
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
        ])
        df_out.to_csv(out_p, index=False)

        # Relatorios vazios
        Path(report_by_analyst_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["assignee", "avg_actual_hours", "sla_met_rate"]).to_csv(report_by_analyst_path, index=False)
        pd.DataFrame(columns=["issue_type", "avg_actual_hours", "sla_met_rate"]).to_csv(report_by_type_path, index=False)
        pd.DataFrame(columns=["issue_type", "avg_actual_hours", "sla_met_rate"]).to_csv(report_by_issue_type_path, index=False)

        print("[GOLD] No Done/Resolved rows with resolved date. Generated empty outputs.")
        return str(out_p)

    # Calculo de SLA (horas uteis)
    def _calc_row(r) -> float:
        return _to_float_hours(calculate_business_hours(_norm_str(r["created"]), _norm_str(r["resolved"])))

    df["actual_hours"] = df.apply(_calc_row, axis=1)

    # SLA esperado por prioridade
    df["priority_norm"] = df["priority"].apply(_norm_priority)
    df["sla_expected_hours"] = df["priority_norm"].map(lambda x: SLA_BY_PRIORITY.get(x, 120.0)).astype(float)

    # SLA atendido
    df["is_sla_met"] = df["actual_hours"] <= df["sla_expected_hours"]

    # Seleciona colunas finais (contrato Gold)
    df_final = df[
        [
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
    ].copy()

    # Persistencia Gold
    gold_p = Path(gold_path)
    gold_p.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(gold_p, index=False)

    # Relatorio por analista (assignee)
    by_analyst = (
        df_final.groupby("assignee", dropna=False)
        .agg(
            avg_actual_hours=("actual_hours", "mean"),
            sla_met_rate=("is_sla_met", "mean"),
        )
        .reset_index()
    )
    by_analyst["avg_actual_hours"] = by_analyst["avg_actual_hours"].round(2)
    by_analyst["sla_met_rate"] = (by_analyst["sla_met_rate"] * 100).round(2)

    # Relatorio por tipo
    by_type = (
        df_final.groupby("issue_type", dropna=False)
        .agg(
            avg_actual_hours=("actual_hours", "mean"),
            sla_met_rate=("is_sla_met", "mean"),
        )
        .reset_index()
    )
    by_type["avg_actual_hours"] = by_type["avg_actual_hours"].round(2)
    by_type["sla_met_rate"] = (by_type["sla_met_rate"] * 100).round(2)

    rep1 = Path(report_by_analyst_path)
    rep2 = Path(report_by_type_path)
    rep3 = Path(report_by_issue_type_path)
    rep1.parent.mkdir(parents=True, exist_ok=True)

    by_analyst.to_csv(rep1, index=False)
    by_type.to_csv(rep2, index=False)
    by_type.to_csv(rep3, index=False)

    print(f"[GOLD] Rows: {len(df_final)}")
    print(f"[GOLD] Generated: {gold_p}")
    print(f"[GOLD] Report analyst: {rep1}")
    print(f"[GOLD] Report type:    {rep2}")
    print(f"[GOLD] Report type2:   {rep3}")

    return str(gold_p)


if __name__ == "__main__":
    calculate_sla()