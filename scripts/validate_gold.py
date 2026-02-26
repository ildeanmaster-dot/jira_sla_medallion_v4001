"""
validate_gold.py
Objetivo:
- Validar artefatos Gold:
  - gold_jira_sla.csv
  - gold_sla_by_analyst.csv
  - gold_sla_by_type.csv (ou gold_sla_by_issue_type.csv)
- Usa as regras centralizadas em src/utils/validators.py

Uso:
  python .\\scripts\\validate_gold.py
"""

from src.utils.validators import validate_gold


if __name__ == "__main__":
    validate_gold(
        gold_path="data/gold/gold_jira_sla.csv",
        report_by_analyst_path="data/gold/gold_sla_by_analyst.csv",
        report_by_type_path="data/gold/gold_sla_by_type.csv",
    )
    print("[VALIDATE] Gold OK")