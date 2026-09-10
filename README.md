# stop-s7

Statystyki dla wariantów przebiegu S7 — ile punktów adresowych znajduje się
w buforze 200 m wokół trasy każdego z wariantów.

## Uruchomienie

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 pobierz_dane.py      # pobiera dane wejściowe (ok. 96 MB, po rozpakowaniu 1,3 GB)
python3 raport.py
```

Wyniki lądują w `raporty/` — dla każdego wariantu plik CSV z adresami
i plik GML z poligonem bufora.

Tryb podglądu warstw w plikach GML:

```bash
python3 raport.py --mode debug
```

## Dane wejściowe

Katalogi `warianty/` i `wojewodztwa-adresy/` nie są trzymane w repozytorium —
po rozpakowaniu zajmują ok. 1,3 GB. Leżą jako assety release'a na GitHubie
i pobiera je `pobierz_dane.py`:

| katalog | zawartość | archiwum |
|---|---|---|
| `warianty/` | pliki GML wariantów A–F | `warianty.tar.gz` (8 MB) |
| `wojewodztwa-adresy/` | shapefile'e PRG dla małopolski | `wojewodztwa-adresy.tar.gz` (88 MB) |

Przydatne opcje:

```bash
python3 pobierz_dane.py --force   # pobierz i rozpakuj od nowa
python3 pobierz_dane.py --keep    # zostaw archiwa w dane-archiwa/
```

Skrypt korzysta tylko z biblioteki standardowej, więc można go uruchomić
przed instalacją zależności. Sprawdza sumy sha256, a przy niezgodności
przerywa i kasuje pobrany plik.

### Źródło danych

Punkty adresowe pochodzą z **Państwowego Rejestru Granic (PRG)**, prowadzonego
przez Główny Urząd Geodezji i Kartografii (GUGiK):

<https://www.geoportal.gov.pl/pl/dane/panstwowy-rejestr-granic-prg/>

Zgodnie z informacją na Geoportalu dane PRG są udostępniane bezpłatnie
i do dowolnego wykorzystania. Wykorzystany zestaw to punkty adresowe
dla województwa małopolskiego (kod 12).

Pliki GML z wariantami przebiegu trasy pochodzą z materiałów
z konsultacji społecznych dotyczących przebiegu S7.

### Wgranie nowej wersji danych

1. Spakuj katalogi:
   ```bash
   mkdir -p dane-archiwa
   tar -czf dane-archiwa/warianty.tar.gz warianty
   tar -czf dane-archiwa/wojewodztwa-adresy.tar.gz wojewodztwa-adresy
   ```
2. Utwórz release z nowym tagiem (np. `dane-v2`) i dołącz oba archiwa jako assety.
3. Podbij `DATA_TAG` w [dane.py](dane.py) i zaktualizuj sumy kontrolne:
   ```bash
   python3 pobierz_dane.py --sumy
   ```

Repozytorium musi być publiczne — dla prywatnego pobieranie assetów
wymagałoby tokena.

## Pliki

- [raport.py](raport.py) — punkt wejścia, obsługa argumentów
- [functions.py](functions.py) — generowanie raportów i tryb debug
- [consts.py](consts.py) — nazwy warstw GML per wariant
- [dane.py](dane.py) — konfiguracja paczek z danymi (tag release'a, sumy kontrolne)
- [pobierz_dane.py](pobierz_dane.py) — pobieranie danych wejściowych
