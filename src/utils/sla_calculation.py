"""
sla_calculation.py
Purpose:
- Centralize SLA business logic (compliance requirement).
- Provide reusable functions:
  - calculate_resolution_hours
  - get_expected_sla_hours
  - is_sla_met
"""

from __future__ import annotations

from typing import Dict

from src.utils.date_utils import calculate_business_hours


SLA_BY_PRIORITY: Dict[str, float] = {
    "high": 24.0,
    "medium": 72.0,
    "low": 120.0,
}


def normalize_priority(priority: str) -> str:
    s = (priority or "").strip().lower()
    if s in {"highest", "high"}:
        return "high"
    if s in {"medium", "med"}:
        return "medium"
    if s in {"lowest", "low"}:
        return "low"
    return "low"


def get_expected_sla_hours(priority: str) -> float:
    p = normalize_priority(priority)
    return float(SLA_BY_PRIORITY.get(p, 120.0))


def calculate_resolution_hours(created_at: str, resolved_at: str) -> float:
    # business-hours calculation is implemented in date_utils
    try:
        return float(calculate_business_hours(created_at, resolved_at))
    except Exception:
        return 0.0


def is_sla_met(resolution_hours: float, expected_sla_hours: float) -> bool:
    try:
        return float(resolution_hours) <= float(expected_sla_hours)
    except Exception:
        return False