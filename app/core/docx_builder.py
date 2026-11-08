"""Generator listy obecności (.docx) – odtwarza układ z wzoru użytkownika.

Dokument powstaje na bazie szablonu (assets/szablon.docx), dzięki czemu zachowuje
style, czcionki i ustawienia strony oryginału (A4, marginesy 2,5 cm).
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import docx
from docx.oxml import parse_xml

from ..paths import resource_path
from .calendar_logic import DayRow, month_total
from .holidays_pl import MONTHS_PL
from .storage import ABSENCE_CODES, Employee, Settings
from .timeutil import format_hours

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

TNR = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
       'w:eastAsia="Times New Roman" w:cs="Times New Roman"/>')
SEGOE = ('<w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" '
         'w:eastAsia="Times New Roman" w:cs="Segoe UI"/>')

# Szerokości kolumn (suma = 9072 twips = szerokość tekstu na A4 przy marginesach 2,5 cm)
COL_WIDTHS = [720, 1380, 1700, 800, 800, 1050, 960, 1662]
HEADERS = ["Dzień", "Dzień tygodnia", "Podpis pracownika", "Od godz.", "Do godz.",
           "Razem godz.", "Uwagi", "Podpis kierownika"]

SHADE = {"saturday": "C6D9F1", "sunday": "D99594", "holiday": "D99594"}


def _run(text: str, *, size: int = 24, bold: bool = False, italic: bool = False,
         fonts: str = TNR, br_after: bool = False) -> str:
    props = fonts + ("<w:b/><w:bCs/>" if bold else "") + ("<w:i/><w:iCs/>" if italic else "")
    props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    t = f'<w:t xml:space="preserve">{escape(text)}</w:t>' if text else ""
    br = "<w:br/>" if br_after else ""
    return f"<w:r><w:rPr>{props}</w:rPr>{t}{br}</w:r>"


def _para(runs: str, *, jc: str = "left", before: int = 0, after: int = 0,
          size: int = 24, fonts: str = TNR, keep_next: bool = False) -> str:
    ppr = ('<w:pStyle w:val="Normal"/>' + ("<w:keepNext/>" if keep_next else "") +
           f'<w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
           f'<w:jc w:val="{jc}"/>'
           f'<w:rPr>{fonts}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>')
    return f"<w:p {NS}><w:pPr>{ppr}</w:pPr>{runs}</w:p>"


def _cell(width: int, text: str = "", *, bold: bool = False, size: int = 22,
          fill: str | None = None) -> str:
    tcpr = f'<w:tcW w:w="{width}" w:type="dxa"/>'
    if fill:
        tcpr += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
    tcpr += '<w:vAlign w:val="center"/>'
    run = _run(text, size=size, bold=bold) if text else ""
    p = (f'<w:p><w:pPr><w:pStyle w:val="Normal"/>'
         f'<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
         f'<w:jc w:val="center"/>'
         f'<w:rPr>{TNR}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr></w:pPr>{run}</w:p>')
    return f"<w:tc><w:tcPr>{tcpr}</w:tcPr>{p}</w:tc>"


def _row(cells: list[str], height: int) -> str:
    return (f'<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="{height}" w:hRule="atLeast"/>'
            f'</w:trPr>{"".join(cells)}</w:tr>')


def _note_cell(width: int, note: str, fill: str | None) -> str:
    # krótkie kody (C, Uw, Nn…) normalną czcionką; dłuższy tekst (np. „Święto”) mniejszą
    size = 22 if len(note) <= 3 else (18 if len(note) <= 7 else 14)
    return _cell(width, note, size=size, fill=fill)


def _table(rows: list[DayRow]) -> str:
    border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    borders = "".join(border.format(s) for s in
                      ("top", "left", "bottom", "right", "insideH", "insideV"))
    total = sum(COL_WIDTHS)
    xml = [f'<w:tbl {NS}><w:tblPr><w:tblStyle w:val="Tabela-Siatka"/>'
           f'<w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>'
           f'<w:tblBorders>{borders}</w:tblBorders><w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="70" w:type="dxa"/>'
           '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar>'
           '<w:tblLook w:val="04a0"/></w:tblPr><w:tblGrid>']
    xml += [f'<w:gridCol w:w="{w}"/>' for w in COL_WIDTHS]
    xml.append("</w:tblGrid>")

    head = [_cell(w, t, bold=True) for w, t in zip(COL_WIDTHS, HEADERS)]
    xml.append(_row(head, 416).replace("<w:cantSplit/>", "<w:cantSplit/><w:tblHeader/>"))

    for r in rows:
        fill = SHADE.get(r.kind) if r.shaded else None
        w = COL_WIDTHS
        cells = [
            _cell(w[0], str(r.day), fill=fill),
            _cell(w[1], r.weekday, fill=fill),
            _cell(w[2], "", fill=fill),
            _cell(w[3], r.start if r.hours is not None else "", fill=fill),
            _cell(w[4], r.end if r.hours is not None else "", fill=fill),
            _cell(w[5], format_hours(r.hours), fill=fill),
            _note_cell(w[6], r.note, fill),
            _cell(w[7], "", fill=fill),
        ]
        xml.append(_row(cells, 340))
    xml.append("</w:tbl>")
    return "".join(xml)


def _legend() -> str:
    runs = []
    items = list(ABSENCE_CODES.items())
    for i, (code, desc) in enumerate(items):
        runs.append(_run(code, size=14, bold=True, fonts=SEGOE))
        sep = ", " if i < len(items) - 1 else "."
        runs.append(_run(f" – {desc}{sep}" + ("" if sep == "." else ""), size=14, fonts=SEGOE))
    return _para("".join(runs), jc="left", before=120, after=0, size=14, fonts=SEGOE)


def _norm_text(emp: Employee, rows: list[DayRow]) -> str:
    if emp.norm_auto:
        return format_hours(month_total(rows)) or "0"
    return (emp.norm_manual or "").strip() or "xx"


def _header_paragraphs(emp: Employee, st: Settings, year: int, month: int,
                       rows: list[DayRow]) -> list[str]:
    jc = "left" if st.header_align == "left" else "center"
    d = st.keep_descriptors
    month_name = MONTHS_PL[month - 1]

    title = _para(_run(st.org_name, bold=True, italic=True), jc=jc, after=240)

    line2 = [_run("Lista obecności – "),
             _run(month_name, bold=True)]
    if d:
        line2.append(_run(" ( miesiąc )"))
    line2 += [_run(f" {year}", bold=True),
              _run(f" ( wymiar czasu pracy  – {_norm_text(emp, rows)} godz. )")]
    p2 = _para("".join(line2), jc=jc, after=120)

    line3 = [_run(f"Dział:  {emp.contract} "), _run(f" {emp.name} ", bold=True)]
    if d:
        line3.append(_run("( imię i nazwisko pracownika )"))
    if d:  # opisy w nawiasach wydłużają linię – system czasu pracy w osobnym wierszu
        line3.append(f"<w:r><w:rPr>{TNR}<w:sz w:val=\"24\"/></w:rPr><w:br/></w:r>")
        line3.append(_run(emp.time_system))
    else:
        line3.append(_run(f", {emp.time_system}"))
    p3 = _para("".join(line3), jc=jc, after=200)
    return [title, p2, p3]


def build_docx(emp: Employee, st: Settings, year: int, month: int,
               rows: list[DayRow], out_path: Path) -> Path:
    template = resource_path("assets/szablon.docx")
    document = docx.Document(str(template))
    body = document.element.body
    sect = body[-1]  # sectPr strony (A4, marginesy 2,5 cm)

    parts = _header_paragraphs(emp, st, year, month, rows) + [_table(rows), _legend()]
    for xml in parts:
        sect.addprevious(parse_xml(xml))

    cp = document.core_properties
    cp.title = f"Lista obecności – {MONTHS_PL[month - 1]} {year} – {emp.name}"
    cp.author = ""
    cp.last_modified_by = ""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(out_path))
    return out_path
