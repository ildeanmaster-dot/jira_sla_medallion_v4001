"""
holiday_api.py
Objetivo:
- Centralizar a obtencao de feriados nacionais do Brasil.
- Retornar um set(date) para ser consumido pelo calculo de SLA.

Por que existe:
- Evita duplicar logica de feriados em varios lugares.
- Permite trocar biblioteca/API no futuro com impacto minimo.

Observacao:
- Aqui usamos a biblioteca 'holidays' (offline).
- Se no futuro voce quiser uma API publica, troca so este modulo.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Set

import holidays


def get_br_holidays(years: Iterable[int]) -> Set[date]:
    """
    Retorna um conjunto de datas (date) com os feriados nacionais do Brasil
    para os anos informados.

    Parametros:
    - years: iterable de anos (ex: [2024, 2025, 2026])

    Retorno:
    - set(date): datas de feriados nacionais
    """
    years_list = sorted(set(int(y) for y in years))
    br = holidays.Brazil(years=years_list)
    return set(br.keys())