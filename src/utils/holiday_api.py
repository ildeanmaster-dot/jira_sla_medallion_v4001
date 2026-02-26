"""
holiday_api.py
Objective:
- Centralize retrieval of Brazilian national holidays.
- Return a set(date) to be consumed by the SLA calculation.

Why it exists:
- Avoids duplicating holiday logic in multiple places.
- Allows swapping out the library/API later with minimal impact.

Note:
- This uses the 'holidays' library (offline).
- If a public API is desired later, only this module needs to change.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Set

import holidays


def get_br_holidays(years: Iterable[int]) -> Set[date]:
    """
    Returns a set of dates representing Brazilian national holidays
    for the provided years.

    Parameters:
    - years: iterable of years (e.g. [2024, 2025, 2026])

    Returns:
    - set(date): national holiday dates
    """
    years_list = sorted(set(int(y) for y in years))
    br = holidays.Brazil(years=years_list)
    return set(br.keys())