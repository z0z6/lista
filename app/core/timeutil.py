"""Parsowanie godzin i obliczanie czasu pracy."""
from __future__ import annotations

import re

_TIME_RE = re.compile(r"^\s*(\d{1,2})(?:[:.,](\d{2}))?\s*$")


def parse_time(text: str | None) -> int | None:
    """'8', '8:00', '08.30' -> minuty od północy; None gdy puste/niepoprawne."""
    if not text:
        return None
    m = _TIME_RE.match(text)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if h > 24 or mi > 59 or (h == 24 and mi > 0):
        return None
    return h * 60 + mi


def format_time(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def normalize_time(text: str | None) -> str:
    """Ujednolica zapis (np. '08.00' -> '8:00'); '' gdy niepoprawny."""
    m = parse_time(text)
    return "" if m is None else format_time(m)


def hours_between(start: str | None, end: str | None) -> float | None:
    """Liczba godzin między 'od' a 'do'. Gdy koniec < początek – praca przez północ."""
    a, b = parse_time(start), parse_time(end)
    if a is None or b is None:
        return None
    if b < a:
        b += 24 * 60
    if b == a:
        return None
    return (b - a) / 60.0


def format_hours(h: float | None) -> str:
    """3.0 -> '3', 3.5 -> '3,5', 3.333 -> '3,33' (polski przecinek)."""
    if h is None:
        return ""
    h = round(h + 1e-9, 2)
    if abs(h - round(h)) < 1e-9:
        return str(int(round(h)))
    return f"{h:.2f}".rstrip("0").rstrip(".").replace(".", ",")
