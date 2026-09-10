# stop-s7

Ile punktów adresowych leży w śladzie projektowanej drogi S7, a ile w strefach
20, 30, 50 i 200 m od niego — dla każdego z wariantów przebiegu A–F.

## Uruchomienie

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 pobierz_dane.py      # dane wejściowe (96 MB, po rozpakowaniu 1,3 GB)
./uruchom.sh                 # policz wszystkie warianty, obiema metodami
```

Przykłady:

```bash
./uruchom.sh --wariant A --metoda dokladna   # jeden wariant, jedna metoda
./uruchom.sh --bez-sladu                     # bez zapisu GPKG
./uruchom.sh --mode debug                    # wykaz warstw w plikach GML
LIMIT=8G ./uruchom.sh                        # podnieś limit pamięci
```

**Licz przez `uruchom.sh`, nie przez `python raport.py`.** Wrapper uruchamia
skrypt w cgroupie z twardym `MemoryMax`. Budowanie śladu to operacje na
geometrii o setkach tysięcy wierzchołków; bez limitu potrafią zająć kilkanaście
GB, a wtedy `systemd-oomd` ubija całą sesję użytkownika — pulpit, przeglądarkę
i edytor — zamiast samego skryptu.

## Co liczy

**Ślad drogi** wyznaczany jest dwiema metodami, podawanymi w raporcie obok siebie:

| metoda | jak | dla kogo |
|---|---|---|
| `dokladna` | obszar między zewnętrznymi liniami skarp — realne zajęcie terenu (śr. 54 m szerokości) | ile adresów fizycznie znika pod drogą |
| `uproszczona` | bufor osi trasy ±30 m | porównanie A–F jednakową miarą |

Warstwy opisujące drogę to linie (krawędzie jezdni, skarpy), nie poligony, więc
metoda dokładna składa z nich obszar przez domknięcie morfologiczne. Szczegóły
i kalibracja promienia: [warstwy.md](warstwy.md).

Wariant **B nie ma w materiałach warstw skarp**, więc liczy się wyłącznie metodą
uproszczoną.

### Tunele

Odcinki tunelowe leżą w osobnej warstwie (`otrasyS7wtunelu_*`, `otrasyBDIwtunelu_*`)
i stanowią od 12% do 26% długości trasy — poza wariantem E, który tuneli nie ma.

Nad tunelem drążonym budynki zostają, ale nad tunelem budowanym metodą odkrywkową
teren jest rozkopany na całej szerokości i budynki znikają tak samo jak na
powierzchni. Raport nie rozstrzyga, która technologia gdzie zostanie użyta —
podaje te adresy w **osobnej kolumnie `nad tunelem`**, żeby dało się je doliczyć
lub odliczyć świadomie:

```
do rozbiórki  =  w śladzie  +  nad tunelem
```

Pas wykopu przyjęto jako ±30 m od osi tunelu — tyle, ile wynosi połowa
zmierzonej szerokości śladu na powierzchni (47,7–57,9 m). Steruje tym
`SZEROKOSC_ODKRYWKI` w [consts.py](consts.py).

**Strefy** są rozłączne (`w śladzie`, `nad tunelem`, `0-20 m`, `20-30 m`,
`30-50 m`, `50-200 m`), a obok nich raport podaje kolumny narastające
(`≤20 m` … `≤200 m`), liczone od krawędzi korytarza — czyli śladu powierzchniowego
razem z pasem nad tunelem.

## Wyniki

W katalogu `raporty/`:

| plik | zawartość |
|---|---|
| `podsumowanie.csv` | wiersz na wariant × metodę, liczby w strefach |
| `rozbiorka.md` | listy adresów do rozbiórki, pogrupowane po miejscowościach |
| `wariant-X-<metoda>-rozbiorka.csv` | te same adresy w formie tabelarycznej |
| `wariant-X-<metoda>-adresy.csv` | wszystkie adresy do 200 m: odległość i strefa |
| `wariant-X-<metoda>-slad.gpkg` | geometria korytarza (warstwy `powierzchnia` i `tunel`) do QGIS |

## Wiarygodność

Materiały źródłowe zawierają gotowy bufor 200 m wokół osi, policzony przez ich
autorów. Zliczenie adresów w tym buforze i porównanie z naszą kolumną `≤200 m`
daje niezależną kontrolę:

| wariant | bufor źródłowy | nasze ≤200 m | różnica |
|---|---|---|---|
| A | 873 | 872 | −0,11% |
| C | 904 | 900 | −0,44% |
| E | 1484 | 1482 | −0,13% |

Kontrolę odpala `functions.kontrola(wariant)`.

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
dla województwa małopolskiego (kod 12) — 856 166 rekordów, EPSG:2180.

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
- [uruchom.sh](uruchom.sh) — uruchamia raport z limitem pamięci
- [functions.py](functions.py) — zliczanie stref, kontrola krzyżowa, tryb debug
- [geometria.py](geometria.py) — budowanie śladu drogi z warstw GML
- [consts.py](consts.py) — wzorce nazw warstw, progi stref, parametry domknięcia
- [warstwy.md](warstwy.md) — inwentarz warstw w plikach GML i kalibracja
- [dane.py](dane.py) — konfiguracja paczek z danymi (tag release'a, sumy kontrolne)
- [pobierz_dane.py](pobierz_dane.py) — pobieranie danych wejściowych
