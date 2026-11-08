"""Wygląd w stylu macOS: jasne tło, zaokrąglone kontrolki, niebieski akcent."""
from __future__ import annotations

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ..paths import resource_path

ACCENT = "#007AFF"
ACCENT_HOVER = "#1A8CFF"
ACCENT_PRESSED = "#0062CC"

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Arial"]


def apply_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(10)
    app.setFont(font)
    icon = resource_path("assets/icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.setStyleSheet(build_qss())


def build_qss() -> str:
    chevron = resource_path("assets/chevron.png").as_posix()
    return f"""
* {{ color: #1D1D1F; }}
QMainWindow, QDialog {{ background: #F5F5F7; }}
QWidget#content {{ background: #F5F5F7; }}

/* ---------- panel boczny ---------- */
QFrame#sidebar {{ background: #E8E8ED; border: none; border-right: 1px solid #D2D2D7; }}
QLabel#appTitle {{ font-size: 15pt; font-weight: 700; }}
QLabel#sectionLabel {{ color: #86868B; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }}
QListWidget#empList {{ background: transparent; border: none; outline: none; }}
QListWidget#empList::item {{ padding: 8px 10px; margin: 1px 0; border-radius: 7px; }}
QListWidget#empList::item:selected {{ background: {ACCENT}; color: white; }}
QListWidget#empList::item:hover:!selected {{ background: #DCDCE2; }}

/* ---------- typografia ---------- */
QLabel#pageTitle {{ font-size: 20pt; font-weight: 700; }}
QLabel#muted {{ color: #86868B; }}
QLabel#hint {{ color: #6E6E73; font-size: 9pt; }}
QLabel#statusOk {{ color: #248A3D; font-size: 9pt; }}
QLabel#statusWarn {{ color: #B25000; font-size: 9pt; }}
QLabel#total {{ font-size: 11pt; font-weight: 600; }}
QLabel#emptyTitle {{ font-size: 18pt; font-weight: 700; }}

/* ---------- karty ---------- */
QFrame#card {{ background: white; border: 1px solid #E0E0E5; border-radius: 12px; }}
QFrame#card QLabel {{ background: transparent; }}

/* ---------- przyciski ---------- */
QPushButton {{
    background: white; border: 1px solid #D1D1D6; border-radius: 7px;
    padding: 6px 14px; min-height: 18px;
}}
QPushButton:hover {{ background: #F2F2F7; }}
QPushButton:pressed {{ background: #E5E5EA; }}
QPushButton:disabled {{ color: #AEAEB2; background: #F5F5F7; }}
QPushButton#primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: #9CC8FF; border-color: #9CC8FF; color: white; }}
QPushButton#danger {{ color: #D70015; }}
QPushButton#nav {{ padding: 4px 10px; font-size: 12pt; min-width: 14px; }}
QPushButton#flat {{ border: none; background: transparent; padding: 6px 8px; text-align: left; color: #3A3A3C; }}
QPushButton#flat:hover {{ background: #DCDCE2; }}

/* ---------- przełącznik segmentowy ---------- */
QFrame#segmented {{ background: #E3E3E8; border-radius: 9px; border: none; }}
QPushButton#seg {{ background: transparent; border: none; border-radius: 7px; padding: 6px 18px; color: #3A3A3C; }}
QPushButton#seg:hover:!checked {{ background: #D8D8DE; }}
QPushButton#seg:checked {{ background: white; font-weight: 600; border: 1px solid #D1D1D6; }}

/* ---------- pola ---------- */
QLineEdit, QTimeEdit, QComboBox, QSpinBox {{
    background: white; border: 1px solid #D1D1D6; border-radius: 7px;
    padding: 5px 9px; min-height: 20px; selection-background-color: {ACCENT}; selection-color: white;
}}
QLineEdit:focus, QTimeEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {ACCENT}; padding: 4px 8px; }}
QLineEdit:disabled, QTimeEdit:disabled, QComboBox:disabled {{ background: #F2F2F7; color: #AEAEB2; }}
QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0; border: none; }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{
    background: white; border: 1px solid #D1D1D6; border-radius: 8px; padding: 4px; outline: none;
    selection-background-color: {ACCENT}; selection-color: white;
}}

/* ---------- tabela miesiąca ---------- */
QTableWidget {{
    background: white; border: 1px solid #E0E0E5; border-radius: 10px;
    gridline-color: #EDEDF0; outline: none; selection-background-color: #CFE4FF; selection-color: #1D1D1F;
}}
QTableWidget::item {{ padding: 2px 6px; }}
QHeaderView::section {{
    background: #FAFAFC; border: none; border-bottom: 1px solid #E0E0E5;
    padding: 7px 6px; font-weight: 600; color: #6E6E73;
}}
QTableCornerButton::section {{ background: #FAFAFC; border: none; }}

/* ---------- paski przewijania ---------- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C7C7CC; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #A8A8AD; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C7C7CC; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{ background: #2C2C2E; color: white; border: none; padding: 5px 8px; border-radius: 6px; }}
QMessageBox {{ background: #F5F5F7; }}
"""
