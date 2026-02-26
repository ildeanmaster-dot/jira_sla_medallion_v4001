"""
validate_bronze.py
Objective:
- Validate the Bronze artifact (data/bronze/bronze_jira.json)
- Use the centralized rules in src/utils/validators.py

Usage:
  python .\\scripts\\validate_bronze.py
"""

from src.utils.validators import validate_bronze


if __name__ == "__main__":
    validate_bronze("data/bronze/bronze_jira.json")
    print("[VALIDATE] Bronze OK")