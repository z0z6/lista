"""Własne kontrolki: przełącznik w stylu macOS/iOS i kontrolka segmentowa."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QRectF, Qt, Property, Signal, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QPushButton


class Switch(QAbstractButton):
    """Przełącznik (pill) z animowaną gałką."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 26)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._user_click = False
        self.toggled.connect(self._on_toggled)

    def nextCheckState(self):
        self._user_click = True      # animujemy tylko kliknięcia użytkownika
        super().nextCheckState()

    def sizeHint(self):
        return QSize(44, 26)

    def _on_toggled(self, on: bool):
        self._anim.stop()
        animate, self._user_click = self._user_click and self.isVisible(), False
        if not animate:                 # zmiana programowa – bez animacji
            self.set_offset(1.0 if on else 0.0)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def get_offset(self) -> float:
        return self._pos

    def set_offset(self, v: float):
        self._pos = v
        self.update()

    offset = Property(float, get_offset, set_offset)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off, on = QColor("#D1D1D6"), QColor("#34C759")
        t = self._pos
        col = QColor(int(off.red() + (on.red() - off.red()) * t),
                     int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t))
        if not self.isEnabled():
            col.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 4
        x = r.left() + 2 + (r.width() - d - 4) * t
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 2, d, d))


class Segmented(QFrame):
    """Kontrolka segmentowa (jak w macOS): wybór jednej z kilku zakładek."""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self._group.addButton(b, i)
            lay.addWidget(b)
        self._group.button(0).setChecked(True)
        self._group.idClicked.connect(self.changed.emit)

    def set_index(self, i: int):
        self._group.button(i).setChecked(True)
        self.changed.emit(i)
