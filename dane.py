"""Konfiguracja paczek z danymi wejściowymi.

Dane (pliki GML wariantów i shapefile'e PRG) są zbyt duże na repozytorium,
więc leżą jako assety release'a na GitHubie. Po wgraniu nowej wersji danych
podbij DATA_TAG i zaktualizuj sumy kontrolne (pobierz_dane.py --sumy).
"""

REPO = "lechup/stop-s7"

# Tag release'a, z którego pobierane są dane.
DATA_TAG = "dane-v1"

# nazwa archiwum -> (katalog, który ma powstać po rozpakowaniu, suma sha256)
ARCHIVES = {
    "warianty.tar.gz": ("warianty", "a85a5997c6e42ad5c972232c67b8a231a8cb6835b24ce9e0b217a4d9d3ec9a2c"),
    "wojewodztwa-adresy.tar.gz": ("wojewodztwa-adresy", "93a11594835318ccd0416b6f12d447350d9890b12d1ed88006d03fa7f8a95769"),
}

DOWNLOAD_URL = "https://github.com/{repo}/releases/download/{tag}/{name}"
