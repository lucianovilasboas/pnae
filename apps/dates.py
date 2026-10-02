"""Utilitários de período/dias da semana para criação em lote."""

from datetime import date, timedelta

# Segunda=0 ... Domingo=6 (igual a date.weekday()).
WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MAX_BULK_ROWS = 400


def iter_dates(start: date, end: date, weekdays: set[int]):
    """Gera as datas no intervalo [start, end] cujo dia da semana está em weekdays."""
    if start is None or end is None or end < start:
        return
    current = start
    step = timedelta(days=1)
    while current <= end:
        if current.weekday() in weekdays:
            yield current
        current += step


def parse_weekdays(values) -> set[int]:
    """Converte valores do formulário (0..6) em um conjunto de dias da semana."""
    out: set[int] = set()
    for value in values:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= index <= 6:
            out.add(index)
    return out
