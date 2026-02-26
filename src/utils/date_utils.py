"""
date_utils.py
Objetivo:
- Calcular horas uteis entre duas datas (ISO) em UTC.
- Excluir fins de semana (sabado/domingo) e feriados nacionais do Brasil.

Definicao de "horas uteis" neste projeto:
- Considera TODOS os minutos do dia quando for dia util (nao limita 09:00-18:00).

Regras de robustez:
- Parsing defensivo:
  - Remove 'Z' ao final
  - datetime.fromisoformat
  - Se vier sem timezone, assume UTC
- Se end < start ou parsing falhar, retorna 0.0
- Contagem minuto a minuto (deterministica)

Dependencia:
- src/utils/holiday_api.py (funcao get_br_holidays)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .holiday_api import get_br_holidays


@dataclass(frozen=True)
class ParsedDateRange:
    start: datetime
    end: datetime


def _parse_iso_utc(dt_str: str) -> Optional[datetime]:
    if dt_str is None:
        return None

    s = str(dt_str).strip()
    if s == "":
        return None

    # Remove 'Z' (UTC)
    if s.endswith("Z"):
        s = s[:-1]

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None

    # Se vier naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def _normalize_range(start_date: str, end_date: str) -> Optional[ParsedDateRange]:
    start_dt = _parse_iso_utc(start_date)
    end_dt = _parse_iso_utc(end_date)

    if start_dt is None or end_dt is None:
        return None

    if end_dt < start_dt:
        return None

    return ParsedDateRange(start=start_dt, end=end_dt)


def calculate_business_hours(start_date: str, end_date: str) -> float:
    """
    Retorna horas uteis entre start_date e end_date (strings ISO).
    Exclui fins de semana e feriados nacionais do Brasil.
    """
    rng = _normalize_range(start_date, end_date)
    if rng is None:
        return 0.0

    start_dt = rng.start
    end_dt = rng.end

    years = list(range(start_dt.year, end_dt.year + 1))
    br_holidays = get_br_holidays(years)

    total_business_minutes = 0
    current = start_dt

    while current < end_dt:
        current_date = current.date()

        is_weekend = current.weekday() >= 5  # 5=sab, 6=dom
        is_holiday = current_date in br_holidays

        if (not is_weekend) and (not is_holiday):
            total_business_minutes += 1

        current += timedelta(minutes=1)

    return float(round(total_business_minutes / 60.0, 2))