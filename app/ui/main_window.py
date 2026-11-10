from __future__ import annotations

import re
import threading
from datetime import date

from PySide6.QtCore import QObject, Qt, QTimer, QTime, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTimeEdit,
                               QVBoxLayout, QWidget)

from ..core.calendar_logic import (DAY_OFF, build_month, default_for, is_task_system,
                                    month_total, monthly_norm_hours)
from ..core.docx_builder import build_docx
from ..core.holidays_pl import MONTHS_PL, WEEKDAYS_PL, fetch_online, offline_holidays
from ..core.storage import (ABSENCE_CODES, FTE_OPTIONS, TIME_SYSTEMS, Employee, Store, fte_factor,
                            fte_weekly_hours)
from ..core.timeutil import format_hours, hours_between, normalize_time
from .settings_dialog import SettingsDialog
from .widgets import Segmented, Switch

ROW_COLORS = {"saturday": "#E3EDFA", "sunday": "#F7DDDC", "holiday": "#F7DDDC"}
COLS = ["Dzień", "Dzień tygodnia", "Od godz.", "Do godz.", "Razem godz.", "Uwagi"]


class _Bridge(QObject):
    fetched = Signal(int, object)


class NoteDelegate(QStyledItemDelegate):
    """Edytowalna lista kodów nieobecności (C, Uw, Nn…) w kolumnie „Uwagi”."""

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.setEditable(True)
        cb.addItem("")
        for code, desc in ABSENCE_CODES.items():
            cb.addItem(f"{code} – {desc}")
        cb.addItem(DAY_OFF)
        return cb

    def setEditorData(self, editor, index):
        cur = index.data(Qt.EditRole) or ""
        i = next((k for k in range(editor.count())
                  if editor.itemText(k).split(" – ")[0] == cur and cur), -1)
        if i >= 0:
            editor.setCurrentIndex(i)
        else:
            editor.setEditText(cur)

    def setModelData(self, editor, model, index):
        text = editor.currentText().strip()
        if " – " in text and text.split(" – ")[0] in ABSENCE_CODES:
            text = text.split(" – ")[0]
        model.setData(index, text, Qt.EditRole)


def make_card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(22, 20, 22, 20)
    lay.setSpacing(12)
    return f, lay


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Listy obecności")
        self.resize(1120, 760)
        self.setMinimumSize(980, 660)

        self.store = Store()
        self.emp: Employee | None = None
        today = date.today()
        self.year, self.month = today.year, today.month
        self._populating = False
        self._rows = []
        self._fetching: set[int] = set()
        self._bridge = _Bridge()
        self._bridge.fetched.connect(self._on_fetched)
        self._save_timer = QTimer(self, singleShot=True, interval=350)
        self._save_timer.timeout.connect(self.store.save)

        self._build_ui()
        self._reload_list()
        self._sync_period_widgets()
        self._refresh_holiday_status()
        self._ensure_holidays(self.year)

    # =====================================================================
    # budowa interfejsu
    # =====================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        content = QWidget()
        content.setObjectName("content")
        root.addWidget(content, 1)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(30, 26, 30, 22)
        cl.setSpacing(16)

        # --- górny pasek: nazwa + wybór miesiąca ---
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("pageTitle")
        top.addWidget(self.title, 1)

        self.btn_prev = QPushButton("‹")
        self.btn_prev.setObjectName("nav")
        self.btn_next = QPushButton("›")
        self.btn_next.setObjectName("nav")
        self.cb_month = QComboBox()
        for m in MONTHS_PL:
            self.cb_month.addItem(m.capitalize())
        self.cb_year = QComboBox()
        for y in range(2020, 2046):
            self.cb_year.addItem(str(y), y)
        self.btn_today = QPushButton("Dziś")
        for w in (self.btn_prev, self.cb_month, self.cb_year, self.btn_next, self.btn_today):
            top.addWidget(w)
        self.btn_prev.clicked.connect(lambda: self._shift_month(-1))
        self.btn_next.clicked.connect(lambda: self._shift_month(1))
        self.btn_today.clicked.connect(self._go_today)
        self.cb_month.activated.connect(self._period_changed)
        self.cb_year.activated.connect(self._period_changed)
        cl.addLayout(top)

        # --- zakładki ---
        seg_row = QHBoxLayout()
        self.seg = Segmented(["Pracownik", "Grafik tygodniowy", "Miesiąc"])
        self.seg.changed.connect(self._page_changed)
        seg_row.addStretch(1)
        seg_row.addWidget(self.seg)
        seg_row.addStretch(1)
        cl.addLayout(seg_row)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_page_employee())
        self.pages.addWidget(self._build_page_schedule())
        self.pages.addWidget(self._build_page_month())
        self.main_stack = QStackedWidget()
        self.main_stack.addWidget(self._build_empty_state())
        self.main_stack.addWidget(self.pages)
        cl.addWidget(self.main_stack, 1)

        # --- dolny pasek ---
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("statusOk")
        bottom.addWidget(self.status, 1)
        self.btn_all = QPushButton("Generuj dla wszystkich")
        self.btn_all.clicked.connect(self.generate_all)
        self.btn_gen = QPushButton("Generuj listę (.docx)")
        self.btn_gen.setObjectName("primary")
        self.btn_gen.clicked.connect(self.generate_current)
        bottom.addWidget(self.btn_all)
        bottom.addWidget(self.btn_gen)
        cl.addLayout(bottom)

    def _build_sidebar(self) -> QFrame:
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(250)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(16, 24, 16, 16)
        lay.setSpacing(8)
        t = QLabel("Listy obecności")
        t.setObjectName("appTitle")
        lay.addWidget(t)
        lay.addSpacing(10)
        sec = QLabel("PRACOWNICY")
        sec.setObjectName("sectionLabel")
        lay.addWidget(sec)
        self.emp_list = QListWidget()
        self.emp_list.setObjectName("empList")
        self.emp_list.currentRowChanged.connect(self._employee_selected)
        lay.addWidget(self.emp_list, 1)

        row = QHBoxLayout()
        add = QPushButton("+ Dodaj")
        add.clicked.connect(self._add_employee)
        self.btn_del = QPushButton("Usuń")
        self.btn_del.setObjectName("danger")
        self.btn_del.clicked.connect(self._delete_employee)
        row.addWidget(add)
        row.addWidget(self.btn_del)
        lay.addLayout(row)

        sett = QPushButton("Ustawienia")
        sett.setObjectName("flat")
        sett.clicked.connect(self._open_settings)
        lay.addWidget(sett)
        return sb

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch(1)
        t = QLabel("Brak pracowników")
        t.setObjectName("emptyTitle")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("Dodaj pierwszego pracownika, aby generować listy obecności.")
        s.setObjectName("muted")
        s.setAlignment(Qt.AlignCenter)
        b = QPushButton("+ Dodaj pracownika")
        b.setObjectName("primary")
        b.clicked.connect(self._add_employee)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addSpacing(10)
        lay.addWidget(b, 0, Qt.AlignCenter)
        lay.addStretch(2)
        return w

    # ---------- strona: dane pracownika ----------
    def _build_page_employee(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        card, cl = make_card()
        g = QGridLayout()
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(14)
        g.setColumnStretch(1, 1)
        cl.addLayout(g)

        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("Imię i nazwisko")
        self.ed_name.textEdited.connect(self._name_edited)
        self.ed_contract = QLineEdit()
        self.ed_contract.textEdited.connect(lambda t: self._set_attr("contract", t))
        self.cb_system = QComboBox()
        self.cb_system.addItems(TIME_SYSTEMS)
        self.cb_system.currentIndexChanged.connect(self._system_changed)
        self.cb_fte = QComboBox()
        for name, _f, _h in FTE_OPTIONS:
            self.cb_fte.addItem(name)
        self.cb_fte.currentIndexChanged.connect(self._fte_changed)
        self.lb_norm_auto = QLabel("")
        self.lb_norm_auto.setObjectName("muted")

        def lab(t):
            l = QLabel(t)
            l.setObjectName("muted")
            return l

        g.addWidget(lab("Imię i nazwisko"), 0, 0)
        g.addWidget(self.ed_name, 0, 1)
        g.addWidget(lab("Dział / rodzaj umowy"), 1, 0)
        g.addWidget(self.ed_contract, 1, 1)
        g.addWidget(lab("Forma pracy"), 2, 0)
        g.addWidget(self.cb_system, 2, 1)
        g.addWidget(lab("Wymiar czasu pracy"), 3, 0)
        g.addWidget(self.cb_fte, 3, 1)
        g.addWidget(self.lb_norm_auto, 4, 1)
        lay.addWidget(card)
        hint = QLabel("Dane zapisują się automatycznie. Forma „zadaniowy” generuje listę kierownika, "
                      "„podstawowy” – zwykłą listę pracownika.")
        hint.setObjectName("hint")
        lay.addWidget(hint)
        lay.addStretch(1)
        return w

    # ---------- strona: grafik tygodniowy ----------
    def _build_page_schedule(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        card, cl = make_card()
        intro = QLabel("Stały grafik pracownika – wypełnia każdy kolejny miesiąc. "
                       "Godziny „Razem” liczą się same.")
        intro.setObjectName("muted")
        cl.addWidget(intro)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        cl.addLayout(g)
        self.sched = []
        for i, name in enumerate(WEEKDAYS_PL):
            sw = Switch(False)
            lb = QLabel(name.capitalize())
            lb.setMinimumWidth(130)
            t1, t2 = QTimeEdit(QTime(8, 0)), QTimeEdit(QTime(16, 0))
            for t in (t1, t2):
                t.setDisplayFormat("H:mm")
                t.setFixedWidth(92)
                t.setAlignment(Qt.AlignCenter)
            tot = QLabel("")
            tot.setObjectName("muted")
            tot.setMinimumWidth(90)
            g.addWidget(sw, i, 0)
            g.addWidget(lb, i, 1)
            g.addWidget(QLabel("od"), i, 2)
            g.addWidget(t1, i, 3)
            g.addWidget(QLabel("do"), i, 4)
            g.addWidget(t2, i, 5)
            g.addWidget(tot, i, 6)
            g.setColumnStretch(7, 1)
            for sig in (sw.toggled, t1.timeChanged, t2.timeChanged):
                sig.connect(lambda *_a, idx=i: self._schedule_changed(idx))
            self.sched.append((sw, t1, t2, tot))
        lay.addWidget(card)
        lay.addStretch(1)
        return w

    # ---------- strona: miesiąc ----------
    def _build_page_month(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.AnyKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setItemDelegateForColumn(5, NoteDelegate(self.table))
        self.table.itemChanged.connect(self._cell_changed)
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        hint = QLabel("Kliknij dwukrotnie „Od / Do / Uwagi”, aby zmienić dzień\n"
                      "(np. kod C, Uw). Zmiany dotyczą tylko tego miesiąca.")
        hint.setObjectName("hint")
        bar.addWidget(hint, 1)
        self.lb_total = QLabel("")
        self.lb_total.setObjectName("total")
        bar.addWidget(self.lb_total)
        reset = QPushButton("Przywróć z grafiku")
        reset.clicked.connect(self._reset_month)
        bar.addWidget(reset)
        lay.addLayout(bar)
        return w

    # =====================================================================
    # pracownicy
    # =====================================================================
    def _reload_list(self, select_id: str | None = None):
        self.emp_list.blockSignals(True)
        self.emp_list.clear()
        for e in self.store.employees:
            it = QListWidgetItem(e.name or "(bez nazwy)")
            it.setData(Qt.UserRole, e.id)
            self.emp_list.addItem(it)
        self.emp_list.blockSignals(False)
        target = select_id or self.store.last_employee
        row = next((i for i, e in enumerate(self.store.employees) if e.id == target), 0)
        if self.store.employees:
            self.emp_list.setCurrentRow(row)
            self._employee_selected(row)
        else:
            self._employee_selected(-1)

    def _employee_selected(self, row: int):
        has = 0 <= row < len(self.store.employees)
        self.emp = self.store.employees[row] if has else None
        self.main_stack.setCurrentIndex(1 if has else 0)
        for b in (self.btn_gen, self.btn_all, self.btn_del, self.seg):
            b.setEnabled(has)
        if not has:
            self.title.setText("Listy obecności")
            return
        self.store.last_employee = self.emp.id
        self.title.setText(self.emp.name or "(bez nazwy)")
        self._load_employee_fields()
        self._load_schedule_fields()
        self._apply_mode()
        self._refresh_month()
        self._mark_dirty()

    def _add_employee(self):
        e = self.store.add_employee()
        self._reload_list(select_id=e.id)
        self.seg.set_index(0)
        self.ed_name.setFocus()
        self.ed_name.selectAll()

    def _delete_employee(self):
        if not self.emp:
            return
        r = QMessageBox.question(self, "Usuń pracownika",
                                 f"Usunąć „{self.emp.name}” wraz z grafikiem i zapisanymi zmianami?",
                                 QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if r == QMessageBox.Yes:
            self.store.remove_employee(self.emp.id)
            self.store.last_employee = ""
            self._reload_list()

    def _mark_dirty(self):
        self._save_timer.start()

    def _set_attr(self, attr: str, value: str):
        if self._populating or not self.emp:
            return
        setattr(self.emp, attr, value)
        self._mark_dirty()

    def _name_edited(self, text: str):
        if self._populating or not self.emp:
            return
        self.emp.name = text
        self.title.setText(text or "(bez nazwy)")
        it = self.emp_list.currentItem()
        if it:
            it.setText(text or "(bez nazwy)")
        self._mark_dirty()

    def _load_employee_fields(self):
        e = self.emp
        self._populating = True
        self.ed_name.setText(e.name)
        self.ed_contract.setText(e.contract)
        self.cb_system.setCurrentIndex(max(TIME_SYSTEMS.index(e.time_system), 0))
        self.cb_fte.setCurrentIndex(max(self.cb_fte.findText(e.fte), 0))
        self._populating = False

    def _system_changed(self, idx: int):
        if self._populating or not self.emp:
            return
        self.emp.time_system = TIME_SYSTEMS[idx]
        self._mark_dirty()
        self._apply_mode()
        self._refresh_month()

    def _fte_changed(self, idx: int):
        if self._populating or not self.emp:
            return
        self.emp.fte = FTE_OPTIONS[idx][0]
        self._mark_dirty()
        self._refresh_month()

    def _norm_hours(self) -> float:
        holidays, _ = self._holidays(self.year)
        return monthly_norm_hours(self.year, self.month, holidays, fte_factor(self.emp.fte))

    def _apply_mode(self):
        """Lista kierownika (zadaniowy): bez grafiku godzinowego i kolumn Od/Do/Razem."""
        task = bool(self.emp) and is_task_system(self.emp)
        self.seg.set_button_visible(1, not task)
        if task and self.pages.currentIndex() == 1:
            self.seg.set_index(0)
        for c in (2, 3, 4):
            self.table.setColumnHidden(c, task)

    # =====================================================================
    # grafik tygodniowy
    # =====================================================================
    def _load_schedule_fields(self):
        self._populating = True
        for i, (sw, t1, t2, tot) in enumerate(self.sched):
            slot = self.emp.schedule.get(str(i))
            on = bool(slot and len(slot) == 2)
            if on:
                for edit, val in ((t1, slot[0]), (t2, slot[1])):
                    h, m = (int(x) for x in normalize_time(val).split(":"))
                    edit.setTime(QTime(h % 24, m))
            sw.setChecked(on)
            t1.setEnabled(on)
            t2.setEnabled(on)
            self._update_slot_total(i)
        self._populating = False

    def _update_slot_total(self, i: int):
        sw, t1, t2, tot = self.sched[i]
        if sw.isChecked():
            h = hours_between(t1.time().toString("H:mm"), t2.time().toString("H:mm"))
            tot.setText(f"= {format_hours(h)} godz." if h else "—")
        else:
            tot.setText("")

    def _schedule_changed(self, i: int):
        if self._populating or not self.emp:
            return
        sw, t1, t2, _ = self.sched[i]
        t1.setEnabled(sw.isChecked())
        t2.setEnabled(sw.isChecked())
        if sw.isChecked():
            self.emp.schedule[str(i)] = [t1.time().toString("H:mm"), t2.time().toString("H:mm")]
        else:
            self.emp.schedule.pop(str(i), None)
        self._update_slot_total(i)
        self._mark_dirty()
        self._refresh_month()

    # =====================================================================
    # miesiąc
    # =====================================================================
    def _holidays(self, year: int):
        cached = self.store.cached_holidays(year)
        if cached:
            return cached
        return offline_holidays(year), "offline"

    def _refresh_month(self):
        if not self.emp:
            return
        holidays, _src = self._holidays(self.year)
        st = self.store.settings
        self._rows = build_month(self.emp, self.year, self.month, holidays, st.holiday_label)
        task = is_task_system(self.emp)
        self._populating = True
        self.table.setRowCount(len(self._rows))
        base_font = self.table.font()
        for r, row in enumerate(self._rows):
            weekday = f"{row.weekday} – ŚWIĘTO" if (task and row.holiday_name) else row.weekday
            vals = [str(row.day), weekday,
                    row.start if row.hours is not None else "",
                    row.end if row.hours is not None else "",
                    format_hours(row.hours), row.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                if c in (0, 1, 4):
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                bg = ROW_COLORS.get(row.kind)
                if bg:
                    it.setBackground(QBrush(QColor(bg)))
                if row.holiday_name:
                    it.setToolTip(row.holiday_name)
                if row.overridden and c in (2, 3, 5):
                    f = QFont(base_font)
                    f.setBold(True)
                    it.setFont(f)
                    it.setForeground(QBrush(QColor("#007AFF")))
                self.table.setItem(r, c, it)
        self._populating = False
        total = month_total(self._rows)
        norm = format_hours(self._norm_hours()) or "0"
        weekly = fte_weekly_hours(self.emp.fte)
        if task:
            self.lb_total.setText(f"Wymiar czasu pracy: {norm} godz.")
        else:
            self.lb_total.setText(f"Zaplanowano: {format_hours(total) or '0'} godz.  ·  Wymiar: {norm} godz.")
        self.lb_norm_auto.setText(f"{weekly} godz. tygodniowo  ·  w tym miesiącu: {norm} godz. "
                                  "(z uwzględnieniem świąt)")

    def _cell_changed(self, item: QTableWidgetItem):
        if self._populating or not self.emp:
            return
        r, c = item.row(), item.column()
        row = self._rows[r]
        text = item.text().strip()
        start, end, note = row.start, row.end, row.note
        label = self.store.settings.holiday_label
        if c in (2, 3):
            norm = normalize_time(text) if text else ""
            if text and not norm:
                self._flash("Niepoprawna godzina – wpisz np. 8:00 lub 12.30", warn=True)
                QTimer.singleShot(0, self._refresh_month)
                return
            if c == 2:
                start = norm
            else:
                end = norm
            note = ""
        elif c == 5:
            note = text
            if note and note != label:
                start = end = ""
        holidays, _ = self._holidays(self.year)
        default = default_for(self.emp, row.date, holidays, label)
        key = row.date.isoformat()
        if (start, end, note) == default:
            self.emp.overrides.pop(key, None)
        else:
            self.emp.overrides[key] = {"from": start, "to": end, "note": note}
        self._mark_dirty()
        QTimer.singleShot(0, self._refresh_month)

    def _reset_month(self):
        if not self.emp:
            return
        prefix = f"{self.year}-{self.month:02d}-"
        keys = [k for k in self.emp.overrides if k.startswith(prefix)]
        if not keys:
            self._flash("Ten miesiąc jest zgodny z grafikiem.")
            return
        r = QMessageBox.question(self, "Przywróć z grafiku",
                                 f"Cofnąć {len(keys)} ręcznych zmian w tym miesiącu?",
                                 QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if r == QMessageBox.Yes:
            for k in keys:
                del self.emp.overrides[k]
            self._mark_dirty()
            self._refresh_month()

    # =====================================================================
    # okres, nawigacja, święta
    # =====================================================================
    def _page_changed(self, i: int):
        self.pages.setCurrentIndex(i)
        if i == 2:
            self._refresh_month()

    def _sync_period_widgets(self):
        self.cb_month.setCurrentIndex(self.month - 1)
        i = self.cb_year.findData(self.year)
        if i < 0:
            self.cb_year.addItem(str(self.year), self.year)
            i = self.cb_year.findData(self.year)
        self.cb_year.setCurrentIndex(i)

    def _period_changed(self, *_):
        self.month = self.cb_month.currentIndex() + 1
        self.year = self.cb_year.currentData()
        self._after_period_change()

    def _shift_month(self, delta: int):
        idx = self.year * 12 + (self.month - 1) + delta
        self.year, self.month = divmod(idx, 12)
        self.month += 1
        self._sync_period_widgets()
        self._after_period_change()

    def _go_today(self):
        t = date.today()
        self.year, self.month = t.year, t.month
        self._sync_period_widgets()
        self._after_period_change()

    def _after_period_change(self):
        self._refresh_holiday_status()
        self._ensure_holidays(self.year)
        self._refresh_month()

    def _ensure_holidays(self, year: int, force: bool = False):
        if not self.store.settings.online_holidays:
            return
        cached = self.store.cached_holidays(year)
        if not force and cached and cached[1] == "online":
            return
        if year in self._fetching:
            return
        self._fetching.add(year)
        self._set_status(f"Pobieram święta {year} z internetu…", warn=False)

        def work():
            self._bridge.fetched.emit(year, fetch_online(year))

        threading.Thread(target=work, daemon=True).start()

    def _on_fetched(self, year: int, data):
        self._fetching.discard(year)
        if data:
            self.store.cache_holidays(year, data, "online")
        elif not self.store.cached_holidays(year):
            self.store.cache_holidays(year, offline_holidays(year), "offline")
        if year == self.year:
            self._refresh_holiday_status()
            self._refresh_month()

    def _refresh_holiday_status(self):
        if not self.store.settings.online_holidays:
            self._set_status(f"Święta {self.year}: wyliczone lokalnie (pobieranie wyłączone)", warn=False)
            return
        c = self.store.cached_holidays(self.year)
        if c and c[1] == "online":
            self._set_status(f"Święta {self.year}: pobrane z internetu ({len(c[0])} dni)", warn=False)
        else:
            self._set_status(f"Święta {self.year}: wyliczone lokalnie (brak połączenia z internetem)",
                             warn=True)

    def _set_status(self, text: str, warn: bool):
        self.status.setText(text)
        self.status.setObjectName("statusWarn" if warn else "statusOk")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _flash(self, text: str, warn: bool = False):
        self._set_status(text, warn)
        QTimer.singleShot(3500, self._refresh_holiday_status)

    # =====================================================================
    # generowanie dokumentów
    # =====================================================================
    @staticmethod
    def _safe_name(name: str) -> str:
        s = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", name).strip().replace(" ", "_")
        return s or "pracownik"

    def _generate_for(self, emp: Employee):
        holidays, _ = self._holidays(self.year)
        st = self.store.settings
        rows = build_month(emp, self.year, self.month, holidays, st.holiday_label)
        fname = f"lista_{MONTHS_PL[self.month - 1]}_{self.year}_{self._safe_name(emp.name)}.docx"
        norm = monthly_norm_hours(self.year, self.month, holidays, fte_factor(emp.fte))
        return build_docx(emp, st, self.year, self.month, rows, st.resolved_output_dir() / fname, norm)

    def generate_current(self):
        if not self.emp:
            return
        if not self.emp.name.strip():
            self._flash("Uzupełnij imię i nazwisko pracownika.", warn=True)
            self.seg.set_index(0)
            self.ed_name.setFocus()
            return
        try:
            path = self._generate_for(self.emp)
        except PermissionError:
            QMessageBox.warning(self, "Nie można zapisać",
                                "Plik jest otwarty w innym programie (np. Word). Zamknij go i spróbuj ponownie.")
            return
        except Exception as ex:  # noqa: BLE001
            QMessageBox.critical(self, "Błąd", f"Nie udało się wygenerować dokumentu:\n{ex}")
            return
        self._done_dialog("Lista została wygenerowana", str(path), path)

    def generate_all(self):
        done, errors = [], []
        for e in self.store.employees:
            if not e.name.strip():
                continue
            try:
                done.append(self._generate_for(e))
            except Exception as ex:  # noqa: BLE001
                errors.append(f"{e.name}: {ex}")
        if not done and not errors:
            return
        folder = self.store.settings.resolved_output_dir()
        text = f"Wygenerowano list: {len(done)}\n{folder}"
        if errors:
            text += "\n\nBłędy:\n" + "\n".join(errors)
        self._done_dialog("Gotowe", text, None)

    def _done_dialog(self, title: str, text: str, file_path):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(f"<b>{title}</b>")
        box.setInformativeText(text)
        open_file = box.addButton("Otwórz plik", QMessageBox.AcceptRole) if file_path else None
        open_dir = box.addButton("Pokaż folder", QMessageBox.ActionRole)
        box.addButton("OK", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if open_file is not None and clicked is open_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))
        elif clicked is open_dir:
            folder = file_path.parent if file_path else self.store.settings.resolved_output_dir()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # =====================================================================
    def _open_settings(self):
        dlg = SettingsDialog(self.store.settings, self)
        if dlg.exec():
            self.store.save()
            self._refresh_holiday_status()
            self._ensure_holidays(self.year)
            self._refresh_month()

    def closeEvent(self, event):
        self._save_timer.stop()
        self.store.save()
        super().closeEvent(event)
