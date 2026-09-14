"""Konfiguracja paczek z danymi wejściowymi.

Dane (pliki GML wariantów i shapefile'e PRG) są zbyt duże na repozytorium,
więc leżą jako assety release'a na GitHubie. Po wgraniu nowej wersji danych
podbij DATA_TAG i zaktualizuj sumy kontrolne (pobierz_dane.py --sumy).
"""

REPO = "lechup/stop-s7"

# Tag release'a, z którego pobierane są dane. Wersjonowanie rocznikiem
# danych (rok.miesiąc), bo wiek danych adresowych jest ich najważniejszą
# właściwością — PRG aktualizowany jest na bieżąco w dni robocze.
DATA_TAG = "v2026.09"

# nazwa archiwum -> (katalog, który ma powstać po rozpakowaniu, suma sha256)
ARCHIVES = {
    "warianty.tar.gz": ("warianty", "a85a5997c6e42ad5c972232c67b8a231a8cb6835b24ce9e0b217a4d9d3ec9a2c"),
    "wojewodztwa-adresy.tar.gz": ("wojewodztwa-adresy", "3edbe7ed303c09d98a3b282db0461ffd3bcbe13ddfedac3ad1f014166aceb21b"),
    "budynki.tar.gz": ("budynki", "e6bfcd39d159bcdcafc15887ba25133319355017f0337d1a78d99e492b0d21fb"),
}

DOWNLOAD_URL = "https://github.com/{repo}/releases/download/{tag}/{name}"
