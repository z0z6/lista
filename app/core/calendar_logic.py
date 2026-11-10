"""Budowanie wierszy miesiąca z grafiku, świąt i zmian jednorazowych."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .holidays_pl import WEEKDAYS_PL
from .storage import Employee
from .timeutil import hours_between, normalize_time


DAY_OFF = "Dzień wolny"


def is_task_system(emp: Employee) -> bool:
    """Zadaniowy system czasu pracy (lista kierownika)."""
    return "zadaniowy" in (emp.time_system or "").lower()


def monthly_norm_hours(year: int, month: int, holidays: dict[date, str], fte: float = 1.0) -> float:
    """Wymiar czasu pracy w miesiącu (art. 130 KP): 8 h x dni pn–pt, pomniejszone o 8 h za
    każde święto przypadające w dniu innym niż niedziela (również w sobotę). Etat = ułamek."""
    weekdays = sum(1 for day in range(1, calendar.monthrange(year, month)[1] + 1)
                   if date(year, month, day).weekday() < 5)
    reducing = sum(1 for h in holidays if h.year == year and h.month == month and h.weekday() != 6)
    return max(weekdays - reducing, 0) * 8 * fte


def compensation_days(year: int, month: int, holidays: dict[date, str]) -> set[date]:
    """Dni wolne za święto w sobotę: najbliższy następny dzień roboczy w miesiącu
    (a gdy go brak – najbliższy poprzedni)."""
    last = calendar.monthrange(year, month)[1]
    result: set[date] = set()

    def free(d: date) -> bool:
        return d.weekday() < 5 and d not in holidays and d not in result

    for hd in sorted(h for h in holidays if h.year == year and h.month == month and h.weekday() == 5):
        cand = next((date(year, month, n) for n in range(hd.day + 1, last + 1)
                     if free(date(year, month, n))), None)
        if cand is None:
            cand = next((date(year, month, n) for n in range(hd.day - 1, 0, -1)
                         if free(date(year, month, n))), None)
        if cand:
            result.add(cand)
    return result


@dataclass
class DayRow:
    day: int
    date: date
    weekday: str
    start: str = ""
    end: str = ""
    note: str = ""
    hours: float | None = None
    holiday_name: str = ""
    kind: str = "work"        # work | saturday | sunday | holiday
    overridden: bool = False

    @property
    def shaded(self) -> bool:
        """Dzień wolny bez wpisanych godzin -> kolorowe tło (jak w oryginalnym wzorze)."""
        return self.kind != "work" and self.hours is None

    @property
    def is_off(self) -> bool:
        return self.kind != "work"


def default_for(emp: Employee, d: date, holidays: dict[date, str], holiday_label: str):
    """Wartości domyślne dnia wynikające z grafiku (bez zmian jednorazowych)."""
    if is_task_system(emp):   # lista kierownika: bez godzin, tylko „Dzień wolny” za święto w sobotę
        return "", "", DAY_OFF if d in compensation_days(d.year, d.month, holidays) else ""
    if d in holidays:
        return "", "", holiday_label
    slot = emp.schedule.get(str(d.weekday()))
    if slot and len(slot) == 2 and slot[0] and slot[1]:
        return normalize_time(slot[0]), normalize_time(slot[1]), ""
    return "", "", ""


def build_month(emp: Employee, year: int, month: int,
                holidays: dict[date, str], holiday_label: str = "Święto") -> list[DayRow]:
    rows: list[DayRow] = []
    task = is_task_system(emp)
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        d = date(year, month, day)
        wd = d.weekday()
        if d in holidays and wd < 5:
            kind = "holiday"
        elif wd == 5:
            kind = "saturday"
        elif wd == 6:
            kind = "sunday"
        else:
            kind = "work"
        start, end, note = default_for(emp, d, holidays, holiday_label)
        ov = emp.overrides.get(d.isoformat())
        overridden = False
        if ov is not None:
            start = normalize_time(ov.get("from", ""))
            end = normalize_time(ov.get("to", ""))
            note = ov.get("note", "")
            overridden = True
        row = DayRow(day=day, date=d, weekday=WEEKDAYS_PL[wd], start=start, end=end,
                     note=note, holiday_name=holidays.get(d, ""), kind=kind,
                     overridden=overridden)
        row.hours = None if task else (
            hours_between(start, end) if not note or note == holiday_label else None)
        rows.append(row)
    return rows


def month_total(rows: list[DayRow]) -> float:
    return sum(r.hours or 0.0 for r in rows)
