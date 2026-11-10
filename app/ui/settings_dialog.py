from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout)

from ..core.storage import Settings
from .widgets import Switch


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia")
        self.setMinimumWidth(620)
        self._s = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(16)
        title = QLabel("Ustawienia")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        self.org = QLineEdit(settings.org_name)
        self._row(grid, 0, "Nagłówek dokumentu", self.org)

        self.out = QLineEdit(str(settings.resolved_output_dir()))
        browse = QPushButton("Wybierz…")
        browse.clicked.connect(self._browse)
        box = QHBoxLayout()
        box.addWidget(self.out, 1)
        box.addWidget(browse)
        self._row(grid, 1, "Folder zapisu", box)

        self.holiday_label = QLineEdit(settings.holiday_label)
        self.holiday_label.setPlaceholderText("np. Święto (puste = bez wpisu)")
        self.holiday_label.setMaxLength(12)
        self._row(grid, 2, "Wpis w „Uwagach” w święta", self.holiday_label)

        self.descr = Switch(settings.keep_descriptors)
        self._row(grid, 3, "Opisy w nawiasach\n(„( miesiąc )”, „( imię i nazwisko )”)", self.descr)

        self.online = Switch(settings.online_holidays)
        self._row(grid, 4, "Pobieraj święta z internetu", self.online)

        hint = QLabel("Gdy internet jest niedostępny, święta są wyliczane lokalnie – "
                      "lista zawsze wygeneruje się poprawnie.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Anuluj")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Zapisz")
        ok.setObjectName("primary")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        root.addLayout(buttons)

    @staticmethod
    def _row(grid: QGridLayout, r: int, label: str, widget):
        lab = QLabel(label)
        lab.setObjectName("muted")
        grid.addWidget(lab, r, 0, Qt.AlignVCenter | Qt.AlignLeft)
        if hasattr(widget, "addWidget"):
            grid.addLayout(widget, r, 1)
        elif isinstance(widget, Switch):
            grid.addWidget(widget, r, 1, Qt.AlignLeft)
        else:
            grid.addWidget(widget, r, 1)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Folder zapisu list", self.out.text())
        if d:
            self.out.setText(d)

    def _accept(self):
        s = self._s
        s.org_name = self.org.text().strip() or s.org_name
        s.output_dir = self.out.text().strip()
        s.holiday_label = self.holiday_label.text().strip()
        s.keep_descriptors = self.descr.isChecked()
        s.online_holidays = self.online.isChecked()
        self.accept()
