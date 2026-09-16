"""Konfiguracja paczek z danymi wejściowymi.

Dane (pliki GML wariantów i shapefile'e PRG) są zbyt duże na repozytorium,
więc leżą jako assety release'a na GitHubie. Po wgraniu nowej wersji danych
podbij DATA_TAG i zaktualizuj sumy kontrolne (pobierz_dane.py --sumy).
"""

REPO = "lechup/stop-s7"

# Tag release'a, z którego pobierane są dane. Niesie OBA roczniki, bo projekt
# opiera się na dwóch źródłach o różnym wieku: dane adresowe PRG (rok.miesiąc,
# aktualizowane na bieżąco w dni robocze) i materiały konsultacyjne STEŚ
# (pełna data wydania, potwierdzona nagłówkiem Last-Modified serwisu).
DATA_TAG = "v2026.09-stes-2025.11.03"

# nazwa archiwum -> (katalog, który ma powstać po rozpakowaniu, suma sha256)
ARCHIVES = {
    "warianty-stes.tar.gz": ("warianty", "41d12b7399ed7ec03c627215a1f30a011983eb9cae49fc4dd568f9ae6863f618"),
    "wojewodztwa-adresy.tar.gz": ("wojewodztwa-adresy", "3edbe7ed303c09d98a3b282db0461ffd3bcbe13ddfedac3ad1f014166aceb21b"),
    "budynki.tar.gz": ("budynki", "e6bfcd39d159bcdcafc15887ba25133319355017f0337d1a78d99e492b0d21fb"),
}

DOWNLOAD_URL = "https://github.com/{repo}/releases/download/{tag}/{name}"
