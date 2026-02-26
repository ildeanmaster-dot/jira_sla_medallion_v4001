"""
transform_jira.py (Silver)
Objetivo:
- Ler o JSON Bronze (copia fiel) e normalizar para uma tabela CSV "enxuta" focada em SLA.

Contrato de saida (colunas):
- issue_id
- issue_key
- created
- resolved
- status
- priority
- issue_type
- assignee

Regras:
- Silver faz limpeza/normalizacao, mas NAO aplica regra de negocio de SLA (isso e Gold).
- Deve ser robusto para JSON aninhado e campos ausentes.
- created e obrigatorio: registros sem created devem ser ignorados.
- Manter itens Open/Em andamento etc. (Gold filtra depois).

Entrada suportada (Bronze):
- dict com chave "issues" (list)
- ou list direta de issues

Observacao:
- Evita pd.read_json para nao ter surpresas com schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _safe_get(obj: Any, path: List[Any]) -> Any:
    """
    Acessa caminho em dict/list de forma defensiva.
    path pode ter chaves (str) e indices (int).
    Retorna None se nao conseguir navegar.
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
    Extrai uma linha normalizada de 1 issue.
    Retorna None se created for invalido/ausente.
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

    # Assignee pode vir como dict, string, ou lista (no seu schema custom)
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

    # Timestamps (schema custom do seu desafio): timestamps[0].created_at / resolved_at
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

    # created e obrigatorio para SLA
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
    Executa a transformacao Silver:
    - Le Bronze JSON
    - Extrai linhas normalizadas
    - Salva CSV Silver
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

    # Padroniza colunas esperadas (mesmo se vier vazio)
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