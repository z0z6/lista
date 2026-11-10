"""Trwałe przechowywanie danych (JSON w %APPDATA%\\ListyObecnosci)."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

from ..paths import data_dir, default_output_dir

DEFAULT_ORG = "Stowarzyszenie “Razem w Dorosłość” -  Warsztat Terapii Zajęciowej “Domino”"

# Forma pracy: podstawowy -> zwykła lista obecności, zadaniowy -> lista kierownika
TIME_SYSTEMS = [
    "podstawowy system czasu pracy",
    "zadaniowy system czasu pracy",
]

# Wymiar czasu pracy: (nazwa, ułamek etatu, godzin tygodniowo)
FTE_OPTIONS = [
    ("cały etat", 1.0, 40),
    ("3/4 etatu", 0.75, 30),
    ("1/2 etatu", 0.5, 20),
    ("1/4 etatu", 0.25, 10),
]


def fte_factor(label: str) -> float:
    return next((f for n, f, _ in FTE_OPTIONS if n == label), 1.0)


def fte_weekly_hours(label: str) -> int:
    return next((h for n, _, h in FTE_OPTIONS if n == label), 40)

ABSENCE_CODES = {
    "C": "choroba",
    "M": "urlop macierzyński",
    "F": "urlop ojcowski",
    "W": "urlop wychowawczy",
    "Op": "opieka",
    "D": "art. 188 KP",
    "Uw": "urlop wypoczynkowy",
    "Ub": "urlop bezpłatny",
    "O": "urlop okolicznościowy",
    "Nu": "inna nieobecność usprawiedliwiona",
    "Nn": "nieobecność nieusprawiedliwiona",
}


@dataclass
class Settings:
    org_name: str = DEFAULT_ORG
    output_dir: str = ""
    holiday_label: str = "Święto"
    keep_descriptors: bool = True      # opisy w nawiasach: "( miesiąc )" itd.
    online_holidays: bool = True

    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir) if self.output_dir else default_output_dir()


@dataclass
class Employee:
    name: str = "Nowy pracownik"
    contract: str = "Umowa o pracę"
    time_system: str = TIME_SYSTEMS[0]  # forma pracy
    fte: str = FTE_OPTIONS[0][0]        # wymiar czasu pracy (etat)
    # grafik tygodniowy: "0"(pn) .. "6"(nd) -> [od, do]
    schedule: dict = field(default_factory=dict)
    # zmiany jednorazowe: "YYYY-MM-DD" -> {"from": "", "to": "", "note": ""}
    overrides: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @staticmethod
    def from_dict(d: dict) -> "Employee":
        e = Employee()
        for k, v in d.items():
            if hasattr(e, k):
                setattr(e, k, v)
        # migracja ze starszych wersji: tylko dwie formy pracy i znane etaty
        e.time_system = TIME_SYSTEMS[1] if "zadaniowy" in str(e.time_system).lower() else TIME_SYSTEMS[0]
        if e.fte not in [n for n, _, _ in FTE_OPTIONS]:
            e.fte = FTE_OPTIONS[0][0]
        return e


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "dane.json")
        self.settings = Settings()
        self.employees: list[Employee] = []
        self.holiday_cache: dict[str, dict] = {}   # "2026" -> {"source","days":{iso:name}}
        self.last_employee: str = ""
        self.load()

    # ---------- I/O ----------
    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            try:
                shutil.copy(self.path, self.path.with_suffix(".uszkodzony.json"))
            except OSError:
                pass
            return
        s = raw.get("settings", {})
        for k, v in s.items():
            if hasattr(self.settings, k):
                setattr(self.settings, k, v)
        self.employees = [Employee.from_dict(e) for e in raw.get("employees", [])]
        self.holiday_cache = raw.get("holiday_cache", {})
        self.last_employee = raw.get("last_employee", "")

    def save(self) -> None:
        raw = {
            "version": 1,
            "settings": asdict(self.settings),
            "employees": [asdict(e) for e in self.employees],
            "holiday_cache": self.holiday_cache,
            "last_employee": self.last_employee,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        if self.path.exists():
            try:
                shutil.copy(self.path, self.path.with_suffix(".bak"))
            except OSError:
                pass
        os.replace(tmp, self.path)

    # ---------- pracownicy ----------
    def get(self, emp_id: str) -> Employee | None:
        return next((e for e in self.employees if e.id == emp_id), None)

    def add_employee(self) -> Employee:
        e = Employee()
        self.employees.append(e)
        self.save()
        return e

    def remove_employee(self, emp_id: str) -> None:
        self.employees = [e for e in self.employees if e.id != emp_id]
        self.save()

    # ---------- święta ----------
    def cached_holidays(self, year: int) -> tuple[dict[date, str], str] | None:
        c = self.holiday_cache.get(str(year))
        if not c:
            return None
        try:
            days = {date.fromisoformat(k): v for k, v in c["days"].items()}
        except Exception:
            return None
        return days, c.get("source", "offline")

    def cache_holidays(self, year: int, days: dict[date, str], source: str) -> None:
        self.holiday_cache[str(year)] = {
            "source": source,
            "days": {d.isoformat(): n for d, n in days.items()},
        }
        self.save()
