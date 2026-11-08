import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import docx

from app.core.calendar_logic import build_month, month_total
from app.core.docx_builder import build_docx
from app.core.holidays_pl import easter_sunday, offline_holidays
from app.core.storage import Employee, Settings, Store
from app.core.timeutil import format_hours, hours_between, normalize_time, parse_time

SCHEDULE = {"2": ["8:00", "11:00"], "4": ["12:00", "16:00"], "0": ["12:00", "15:00"]}


def test_time_parsing_and_hours():
    assert parse_time("8") == 480 and parse_time("08.30") == 510 and parse_time("25:00") is None
    assert normalize_time("08:00") == "8:00"
    assert hours_between("8:00", "11:00") == 3
    assert hours_between("12:00", "15:30") == 3.5
    assert hours_between("22:00", "6:00") == 8          # praca przez północ
    assert format_hours(3) == "3" and format_hours(3.5) == "3,5" and format_hours(None) == ""


def test_polish_holidays_2026():
    assert easter_sunday(2026) == date(2026, 4, 5)
    h = offline_holidays(2026)
    assert date(2026, 4, 6) in h and date(2026, 5, 24) in h and date(2026, 6, 4) in h
    assert date(2026, 12, 24) in h and len(h) == 14
    assert date(2024, 12, 24) not in offline_holidays(2024)


def test_month_hours_july_2026():
    e = Employee(name="Jan", schedule=SCHEDULE)
    rows = build_month(e, 2026, 7, offline_holidays(2026))
    assert len(rows) == 31
    assert month_total(rows) == 47   # 5*3 (śr) + 5*4 (pt) + 4*3 (pn)
    assert rows[30].hours == 4       # 31 lipca (piątek) 12:00-16:00


def test_holiday_removes_scheduled_hours_and_override():
    e = Employee(name="Jan", schedule=SCHEDULE,
                 overrides={"2026-11-04": {"from": "", "to": "", "note": "Uw"}})
    rows = build_month(e, 2026, 11, offline_holidays(2026))
    assert rows[10].kind == "holiday" and rows[10].hours is None   # 11.11 (środa) – święto
    assert rows[3].note == "Uw" and rows[3].hours is None          # 4.11 – urlop


def test_docx_structure(tmp_path):
    e = Employee(name="Jan Kowalski", schedule=SCHEDULE)
    rows = build_month(e, 2026, 7, offline_holidays(2026))
    out = build_docx(e, Settings(), 2026, 7, rows, tmp_path / "x.docx")
    d = docx.Document(str(out))
    t = d.tables[0]
    assert len(t.rows) == 32 and len(t.columns) == 8
    assert t.cell(0, 0).text == "Dzień"
    assert t.cell(1, 3).text == "8:00" and t.cell(1, 4).text == "11:00" and t.cell(1, 5).text == "3"
    text = "\n".join(p.text for p in d.paragraphs)
    assert "lipiec" in text and "2026" in text and "Jan Kowalski" in text and "47 godz." in text


def test_storage_roundtrip(tmp_path):
    s = Store(tmp_path / "d.json")
    e = s.add_employee()
    e.name = "Anna"
    e.schedule = SCHEDULE
    e.overrides["2026-07-08"] = {"from": "", "to": "", "note": "C"}
    s.cache_holidays(2026, offline_holidays(2026), "online")
    s.save()
    s2 = Store(tmp_path / "d.json")
    assert s2.employees[0].name == "Anna" and s2.employees[0].overrides["2026-07-08"]["note"] == "C"
    assert s2.cached_holidays(2026)[1] == "online"
