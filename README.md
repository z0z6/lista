# Listy obecności (Windows)

Prosta aplikacja do generowania ujednoliconych list obecności (.docx) dla pracowników
– w układzie zgodnym ze wzorem „Warsztat Terapii Zajęciowej Domino”.

## Co robi
- **Pracownicy** – dodajesz raz, dane (imię i nazwisko, umowa, system czasu pracy, grafik) są pamiętane.
- **Grafik tygodniowy** – ustawiasz dni i godziny od–do; „Razem godz.” liczy się samo.
- **Miesiąc** – podgląd tabeli; można zmienić pojedynczy dzień (godziny albo kod nieobecności C, Uw, Nn…).
  Zmiany dotyczą tylko danego miesiąca i też są zapisywane.
- **Święta** – pobierane z internetu (API Nager.Date), z automatycznym zapasem offline
  (wyliczanie Wielkanocy, Bożego Ciała itd.). Dni wolne są podświetlane tak jak we wzorze
  (sobota – niebieski, niedziela/święto – czerwony).
- **Generuj** – tworzy gotowy .docx (A4, wyśrodkowana tabela, te same czcionki co we wzorze).

Dane: `%APPDATA%\ListyObecnosci\dane.json`. Domyślny folder zapisu: `Dokumenty\Listy obecności`
(zmienisz w *Ustawieniach*).

## Budowanie EXE (GitHub Actions)
1. Wgraj całą zawartość tego katalogu do repozytorium na GitHubie.
2. Zakładka **Actions** → *Build Windows EXE* wykona się automatycznie po pushu
   (lub uruchom ręcznie: *Run workflow*).
3. Gotowy plik pobierzesz z **Artifacts** → `ListyObecnosci-windows` (`ListyObecnosci.exe`).
4. Po otagowaniu (`git tag v1.0.0 && git push --tags`) plik trafi też do **Releases**.

## Uruchomienie lokalnie (opcjonalnie)
```
pip install -r requirements.txt
python main.py
```
Testy: `pip install -r requirements-dev.txt && python -m pytest`.
