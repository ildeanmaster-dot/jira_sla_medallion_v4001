"""
validate_gold.py
Objective:
- Validate Gold artifacts:
  - gold_jira_sla.csv
  - gold_sla_by_analyst.csv
  - gold_sla_by_type.csv (or gold_sla_by_issue_type.csv)
- Use centralized rules in src/utils/validators.py

Usage:
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