import ctypes
import os
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.style import apply_style


def main() -> int:
    if os.name == "nt":  # poprawna ikona na pasku zadań
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ListyObecnosci.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Listy obecności")
    apply_style(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
