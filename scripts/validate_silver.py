"""
validate_silver.py
Objective:
- Validate the Silver artifact (data/silver/silver_jira.csv)
- Use rules from src/utils/validators.py

Usage:
  python .\\scripts\\validate_silver.py
"""

from src.utils.validators import validate_silver


if __name__ == "__main__":
    validate_silver("data/silver/silver_jira.csv")
    print("[VALIDATE] Silver OK")