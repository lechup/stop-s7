# stop-s7

Ile punktów adresowych leży w śladzie projektowanej drogi S7, a ile w strefach
20, 30, 50 i 200 m od niego — dla każdego z wariantów przebiegu A–F.

## Uruchomienie

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 pobierz_dane.py      # dane wejściowe (96 MB, po rozpakowaniu 1,3 GB)
./uruchom.sh                 # policz wszystkie warianty
```

Przykłady:

```bash
./uruchom.sh --wariant A --wariant C   # wybrane warianty
./uruchom.sh --bez-sladu               # bez zapisu GPKG
./uruchom.sh --mode debug              # wykaz warstw w plikach GML
./uruchom.sh --mode margines           # przelicz średni margines skarp
./uruchom.sh --mode dane               # na jakich danych skrypt liczy
./uruchom.sh --adres "Osterwy 41P"     # sprawdź pojedynczy adres
LIMIT=8G ./uruchom.sh                  # podnieś limit pamięci
```

**Licz przez `uruchom.sh`, nie przez `python raport.py`.** Wrapper uruchamia
skrypt w cgroupie z twardym `MemoryMax`. Budowanie śladu to operacje na
geometrii o setkach tysięcy wierzchołków; bez limitu potrafią zająć kilkanaście
GB, a wtedy `systemd-oomd` ubija całą sesję użytkownika — pulpit, przeglądarkę
i edytor — zamiast samego skryptu.

## Co liczy

**Ślad drogi** to obszar między zewnętrznymi liniami skarp — teren faktycznie
zajęty pod budowę, średnio 46–49 m szerokości. Warstwy opisujące drogę to linie
(krawędzie jezdni, skarpy), nie poligony, więc ślad składany jest z nich przez
domknięcie morfologiczne. Szczegóły i kalibracja: [warstwy.md](warstwy.md).

### Wariant B jest szacowany

Materiały nie zawierają dla wariantu B warstw skarp — ma tylko krawędzie jezdni.
Jego ślad liczony jest więc z samego pobocza i poszerzany o średni margines skarp
zmierzony na pozostałych wariantach:

| wariant | margines skarp na stronę |
|---|---|
| A | +8,7 m |
| C | +9,2 m |
| D | +5,3 m |
| E | +5,6 m |
| F | +9,6 m |
| **średnia** | **+7,7 m** |

Ślad wariantu B powstaje więc z jego własnych krawędzi jezdni, poszerzonych
o 7,7 m w każdą stronę. Rozrzut źródłowy (od +5,3 do +9,6 m) przekłada się na
niepewność rzędu ±2 m szerokości śladu, więc **liczby dla B są szacunkiem** —
oznaczonym w kolumnie `szacunek` w podsumowaniu i nagłówkiem w `rozbiorka.md`.

Margines siedzi w `MARGINES_SKARP` w [consts.py](consts.py); przelicza go
`./uruchom.sh --mode margines`.

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
| `podsumowanie.csv` | wiersz na wariant, liczby w strefach, kolumna `szacunek` |
| `rozbiorka.md` | listy adresów do rozbiórki, pogrupowane po miejscowościach |
| `wariant-X-rozbiorka.csv` | te same adresy w formie tabelarycznej |
| `wariant-X-adresy.csv` | wszystkie adresy do 200 m: odległość i strefa |
| `wariant-X-slad.gpkg` | geometria korytarza (warstwy `powierzchnia` i `tunel`) do QGIS |

## Sprawdzanie pojedynczego adresu

```bash
./uruchom.sh --adres "Osterwy 41P"     # ulica i numer
./uruchom.sh --adres "Golkowice 116"   # adres wiejski, bez ulicy
./uruchom.sh --adres "Osterwy"         # sama ulica — skrót do najbliższego wariantu
```

Dla podanego adresu wypisuje odległość i strefę w każdym z wariantów:

```
Juliusza Osterwy 41P, 30-699 Kraków
  wariant     od korytarza   od powierzchni   strefa
  A                3215.9m          3215.9m   poza 200 m
  B                 100.9m           152.0m   50-200 m  [SZACUNEK]
  C                 691.4m           691.4m   poza 200 m
```

Kolumna `od powierzchni` liczona jest z pominięciem pasa nad tunelem, więc różnica
między nią a `od korytarza` pokazuje, że najbliżej przebiega odcinek tunelowy.

Tryb korzysta z zapisanych plików `wariant-X-slad.gpkg`, więc odpowiada od razu —
ale wymaga wcześniejszego przeliczenia (`./uruchom.sh`).

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

### Rozpoznawanie pliku adresowego

Skrypt nie polega na nazwie pliku, tylko szuka pod `wojewodztwa-adresy/`
czegokolwiek pasującego do `*PunktyAdresowe*.shp` i wybiera plik, który **ma
wymagane kolumny**. Powód: GUGiK od 1 lipca 2026 publikuje dane adresowe tylko
w nowej strukturze i usunął przy tym prefiks `NOWE_`. Plik nazywa się teraz
`PRG_PunktyAdresowe_*` — ale dokładnie taką nazwę nosiła wcześniej **stara**
struktura, o zupełnie innych polach:

| struktura | pola |
|---|---|
| stara (wycofana) | `TERYT, PNA, SIMC_id, SIMC_nazwa, ULIC_id, ULIC_nazwa, Numer` |
| nowa (używana) | `ID_IIP, NUMER_PORZ, KOD_POCZT, DATA_NAD, NAZWA_ULC, NAZWA_GMI, NAZWA_MSC, ...` |

Sama nazwa nie mówi więc nic. Jeśli żaden znaleziony plik nie ma wymaganych
kolumn, skrypt przerywa i mówi wprost, że to prawdopodobnie stara struktura.

`./uruchom.sh --mode dane` pokazuje, który plik został wybrany, ile ma rekordów
i do kiedy sięgają dane (najnowsza sensowna data nadania adresu).

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
2. Utwórz release z tagiem nazwanym rocznikiem danych (`v2026.09` dla danych
   z września 2026) i dołącz archiwa oraz raporty jako assety.
3. Podbij `DATA_TAG` w [dane.py](dane.py) i zaktualizuj sumy kontrolne:
   ```bash
   python3 pobierz_dane.py --sumy
   ```

Repozytorium musi być publiczne — dla prywatnego pobieranie assetów
wymagałoby tokena.

Tagi wersjonowane są **rocznikiem danych** (`rok.miesiąc`), a nie numerem
kolejnym — wiek danych adresowych jest ich najważniejszą właściwością, bo PRG
aktualizowany jest na bieżąco w dni robocze. Jeden release zawiera komplet
z danego rocznika: archiwa wejściowe i wyliczone z nich raporty, żeby nie dało
się pomylić, które wyniki pochodzą z których danych.

## Pliki

- [raport.py](raport.py) — punkt wejścia, obsługa argumentów
- [uruchom.sh](uruchom.sh) — uruchamia raport z limitem pamięci
- [functions.py](functions.py) — zliczanie stref, kontrola krzyżowa, tryb debug
- [geometria.py](geometria.py) — budowanie śladu drogi z warstw GML
- [consts.py](consts.py) — wzorce nazw warstw, progi stref, parametry domknięcia
- [warstwy.md](warstwy.md) — inwentarz warstw w plikach GML i kalibracja
- [dane.py](dane.py) — konfiguracja paczek z danymi (tag release'a, sumy kontrolne)
- [pobierz_dane.py](pobierz_dane.py) — pobieranie danych wejściowych
