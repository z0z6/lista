"""Ścieżki: zasoby (działa także po spakowaniu PyInstallerem) i katalog danych."""
import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / rel


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        d = base / "ListyObecnosci"
    else:
        d = Path.home() / ".listy_obecnosci"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_output_dir() -> Path:
    docs = Path.home() / "Documents"
    base = docs if docs.exists() else Path.home()
    return base / "Listy obecności"
