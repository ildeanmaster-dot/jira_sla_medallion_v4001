"""
holiday_api.py
Purpose:
- Fetch Brazilian national holidays from a PUBLIC API (compliance requirement).
- Return a set(date) for SLA/business-hours calculations.
- Implement simple local cache to avoid repeated requests.

API chosen:
- BrasilAPI: https://brasilapi.com.br/api/feriados/v1/{year}

Notes:
- If the API is unavailable, we fail fast by raising an exception.
  (This is deliberate to keep compliance explicit; fallback behavior can be added if needed.)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Set

import requests


def _cache_path(year: int) -> Path:
    return Path("data") / "cache" / f"holidays_br_{year}.json"


def _ensure_cache_dir() -> None:
    (Path("data") / "cache").mkdir(parents=True, exist_ok=True)


def get_br_holidays(years: Iterable[int]) -> Set[date]:
    """
    Fetch Brazilian national holidays for the given years using BrasilAPI.
    Returns a set of `date` objects.
    """
    years_list = sorted(set(int(y) for y in years))
    holidays: Set[date] = set()

    _ensure_cache_dir()

    for y in years_list:
        cp = _cache_path(y)

        if cp.exists():
            payload = json.loads(cp.read_text(encoding="utf-8"))
        else:
            url = f"https://brasilapi.com.br/api/feriados/v1/{y}"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            cp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        # BrasilAPI returns items like: {"date":"2026-01-01","name":"Confraternização Universal","type":"national"}
        for item in payload:
            ds = item.get("date")
            if not ds:
                continue
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
                holidays.add(d)
            except Exception:
                # ignore invalid dates from API response defensively
                continue

    return holidays