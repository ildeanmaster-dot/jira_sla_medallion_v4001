"""
validate_silver.py
Objetivo:
- Validar o artefato Silver (data/silver/silver_jira.csv)
- Usa as regras do src/utils/validators.py

Uso:
  python .\\scripts\\validate_silver.py
"""

from src.utils.validators import validate_silver


if __name__ == "__main__":
    validate_silver("data/silver/silver_jira.csv")
    print("[VALIDATE] Silver OK")