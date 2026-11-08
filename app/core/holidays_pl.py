"""Polskie święta (dni ustawowo wolne od pracy).

Źródło główne: API Nager.Date (internet). Zapasowe: obliczenia lokalne
(działają offline, więc aplikacja nigdy nie zostaje bez kalendarza).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta

API_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/PL"

WEEKDAYS_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MONTHS_PL = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
             "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"]


def easter_sunday(year: int) -> date:
    """Algorytm Meeusa/Jonesa/Butchera (kalendarz gregoriański)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def offline_holidays(year: int) -> dict[date, str]:
    easter = easter_sunday(year)
    days = {
        date(year, 1, 1): "Nowy Rok",
        date(year, 1, 6): "Trzech Króli",
        easter: "Wielkanoc",
        easter + timedelta(days=1): "Poniedziałek Wielkanocny",
        date(year, 5, 1): "Święto Pracy",
        date(year, 5, 3): "Święto Konstytucji 3 Maja",
        easter + timedelta(days=49): "Zielone Świątki",
        easter + timedelta(days=60): "Boże Ciało",
        date(year, 8, 15): "Wniebowzięcie NMP",
        date(year, 11, 1): "Wszystkich Świętych",
        date(year, 11, 11): "Święto Niepodległości",
        date(year, 12, 25): "Boże Narodzenie (1. dzień)",
        date(year, 12, 26): "Boże Narodzenie (2. dzień)",
    }
    if year >= 2025:  # Wigilia – dzień wolny od 2025 r.
        days[date(year, 12, 24)] = "Wigilia Bożego Narodzenia"
    return days


def fetch_online(year: int, timeout: float = 8.0) -> dict[date, str] | None:
    """Pobiera święta z internetu. None przy braku sieci / błędnej odpowiedzi."""
    try:
        req = urllib.request.Request(
            API_URL.format(year=year),
            headers={"User-Agent": "ListyObecnosci/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        result: dict[date, str] = {}
        for item in payload:
            types = item.get("types") or ["Public"]
            if "Public" not in types:
                continue
            d = date.fromisoformat(item["date"])
            if d.year == year:
                result[d] = item.get("localName") or item.get("name") or "Święto"
        # kontrola sensowności – w Polsce jest min. 13 dni ustawowych
        return result if len(result) >= 12 else None
    except Exception:
        return None
