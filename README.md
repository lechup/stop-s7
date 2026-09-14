# stop-s7

Ile punktów adresowych leży w śladzie projektowanej drogi S7, a ile w strefach
20, 30, 50 i 200 m od niego — dla każdego z wariantów przebiegu A–F.

## Uruchomienie

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 pobierz_dane.py      # dane wejściowe (54 MB, po rozpakowaniu 790 MB)
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
| `wariant-X-slad.gpkg` | do QGIS: warstwy `korytarz`, `budynki` i `adresy` |

### Adresy a budynki — dwie różne miary

Podsumowanie podaje obok siebie liczby liczone **z punktów adresowych PRG**
i **z obrysów budynków EGiB**. To nie jest ta sama wielkość policzona dwa razy,
tylko dwie niezależne miary, i nie należy ich mylić:

- punkt adresowy to jedna współrzędna — jeden budynek może mieć kilka adresów
  albo nie mieć żadnego (garaże, stodoły, budynki gospodarcze),
- obrys budynku to rzeczywisty kształt — budynek stojący w śladzie połową
  liczy się jako trafiony, bo pas zajęcia terenu i tak go obejmuje,
- EGiB liczy wszystko, co stoi, dlatego obok kolumny `budynki` jest
  `budynki mieszkalne` (`RODZAJ = 'm'`), i to ona jest porównywalna
  z liczbą adresów.

Budynki liczone są w **tej samej siatce stref co adresy** — `w śladzie`,
`nad tunelem`, `0-20 m`, `20-30 m`, `30-50 m`, `50-200 m` plus kolumny
narastające `≤20 m` … `≤200 m`, wszystkie z przedrostkiem `budynki`. Strefę
rozstrzyga odległość do najbliższej części korytarza, dokładnie jak przy
adresach; `budynki mieszkalne` dotyczy samego korytarza, bo tam rozstrzyga się
rozbiórka.

Skala rozbieżności dla śladu z pasem nad tunelem:

| wariant | adresy „do rozbiórki" | budynki | budynki mieszkalne |
|---|---|---|---|
| A | 116 | 225 | 132 |
| B | 110 | 197 | 117 |
| C | 150 | 266 | 160 |
| D | 69 | 144 | 78 |
| E | 61 | 123 | 74 |
| F | 115 | 216 | 130 |

Dwukrotna różnica w kolumnie `budynki` to w większości zabudowa gospodarcza.
Po zawężeniu do mieszkalnych zostaje kilkanaście procent w górę względem
liczby adresów.

Pokrycie obu zbiorów nie jest pełne: w korytarzu wariantu A **76%** punktów
adresowych leży wewnątrz jakiegoś obrysu z EGiB (w samym śladzie 70%).
Pozostałe to punkty postawione obok budynku, działki z adresem bez zabudowy
albo braki w ewidencji — raport tego nie rozstrzyga.

Budynki są **opcjonalne**: jeśli `budynki/budynki.gpkg` nie ma, raport liczy się
jak dotąd, tylko bez kolumn budynkowych.

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
| A | 903 | 902 | −0,11% |
| C | 908 | 904 | −0,44% |
| E | 1495 | 1493 | −0,13% |

Kontrolę odpala `functions.kontrola(wariant)`.

## Mapa online

Statyczna strona z mapą wariantów i wyszukiwarką adresu, wystawiana przez
GitHub Pages z katalogu [docs/](docs/):

<https://lechup.github.io/stop-s7/>

Wpisanie adresu pokazuje odległość i strefę we wszystkich wariantach naraz —
to odpowiednik trybu `--adres`, tyle że w przeglądarce. Widok zapisuje się
w adresie URL (`#C/17/49.9454/19.9742`), więc da się podesłać komuś link
prosto na jego ulicę.

Dane generuje [eksport_web.py](eksport_web.py):

```bash
.venv/bin/python eksport_web.py
```

| plik | zawartość | po gzipie |
|---|---|---|
| `docs/dane/wariant-X.geojson` | korytarz, budynki i adresy jednego wariantu | 40–58 kB |
| `docs/dane/adresy-index.json` | 13 641 adresów z odległością do każdego wariantu | 356 kB |

Całość waży 662 kB po kompresji, więc nie ma po co sięgać po kafelki wektorowe —
przeglądarka bierze zwykły GeoJSON, a Pages sam serwuje gzip. Indeks wyszukiwarki
wczytywany jest dopiero przy pierwszym wpisaniu adresu, żeby wejście na stronę
kosztowało ~60 kB.

Indeks obejmuje adresy do **500 m** od któregokolwiek wariantu, czyli dalej niż
raportowe 200 m — ktoś mieszkający tuż za granicą strefy dostaje konkretną liczbę
zamiast „nie znaleziono".

Dwie rzeczy warte uwagi przy zmianach:

- **`allow_nan=False` przy zapisie JSON-a.** Braki w danych to `NaN`, a `NaN`
  jest w Pythonie logicznie prawdziwy, więc `wartość or ""` go przepuszcza.
  `json.dump` zapisuje wtedy literał `NaN`, którego `JSON.parse` w przeglądarce
  **nie przyjmuje** — a Python taki plik czyta bez mrugnięcia, więc błąd
  przechodzi testy i wysypuje się dopiero u użytkownika.
- **Kafelki podkładu pochodzą z serwerów OpenStreetMap.** Przy większym ruchu
  wypada przejść na własny lub płatny serwis kafelków — polityka OSM dopuszcza
  lekkie użycie, nie ruch z kampanii.

## Dane wejściowe

Katalogi `warianty/`, `wojewodztwa-adresy/` i `budynki/` nie są trzymane
w repozytorium — po rozpakowaniu zajmują ok. 790 MB. Leżą jako assety release'a
na GitHubie i pobiera je `pobierz_dane.py`:

| katalog | zawartość | archiwum |
|---|---|---|
| `warianty/` | pliki GML wariantów A–F | `warianty.tar.gz` (8 MB) |
| `wojewodztwa-adresy/` | punkty adresowe PRG dla małopolski | `wojewodztwa-adresy.tar.gz` (44 MB) |
| `budynki/` | obrysy budynków EGiB przy korytarzu | `budynki.tar.gz` (1 MB) |

Przydatne opcje:

```bash
python3 pobierz_dane.py --force   # pobierz i rozpakuj od nowa
python3 pobierz_dane.py --keep    # zostaw archiwa w dane-archiwa/
```

Skrypt korzysta tylko z biblioteki standardowej, więc można go uruchomić
przed instalacją zależności. Sprawdza sumy sha256, a przy niezgodności
przerywa i kasuje pobrany plik.

### Obrysy budynków (EGiB)

Punkt adresowy PRG to współrzędna, a nie obrys budynku — dom może stać kilka
metrów od punktu. Obrysy z **Ewidencji Gruntów i Budynków** pozwalają liczyć
trafienia po rzeczywistym kształcie budynku.

Pobiera je [pobierz_budynki.py](pobierz_budynki.py) ze zbiorczej usługi WFS
prowadzonej przez GUGiK:

<https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza>

Usługa agreguje dane z 385 powiatowych usług WFS — EGiB prowadzą starostwa —
i odświeżana jest w cyklu codziennym. Dane EGiB co do zasady są płatne, ale
geometria działek i budynków wraz z podstawowymi atrybutami jest **bezpłatna
i do dowolnego wykorzystania**; tylko z tego korzystamy (obrys, `RODZAJ`, liczba
kondygnacji). Specyfikację usługi określa rozporządzenie Ministra Rozwoju, Pracy
i Technologii z 27 lipca 2021 r. w sprawie ewidencji gruntów i budynków.

```bash
.venv/bin/python pobierz_budynki.py
```

Zwykle nie trzeba tego uruchamiać — `pobierz_dane.py` ściąga gotową migawkę
z release'a. `pobierz_budynki.py` przydaje się, gdy chcesz świeże dane
(EGiB zmienia się codziennie) albo inny zasięg po zmianie wariantów.

Zakres pobierania to wspólny korytarz wszystkich wariantów poszerzony o 200 m
(49 km²) — dokładnie tyle, ile potrzeba do wypełnienia całej tabeli wyników.
Odpytujemy prostokątem opisanym na tym obszarze, bo filtr WFS ma być krótki
i prosty, a do właściwego kształtu przycinamy już lokalnie. Wynik to
`budynki/budynki.gpkg` — 8 971 budynków, 2,9 MB.

Dwie rzeczy, o które przy tej usłudze łatwo się potknąć:

- **Kolejność osi.** Przy `srsName="urn:ogc:def:crs:EPSG::2180"` współrzędne idą
  jako `northing easting`, odwrotnie niż podaje GeoPandas. Zamiana miejscami nie
  kończy się błędem ani pustką — serwer zwraca komplet budynków, tylko z innego
  miejsca w Polsce. Skrypt po pobraniu sprawdza, czy geometria wpada w korytarz.
- **Limit 1000 obiektów na żądanie** jest twardy: przy `count=5000` serwer i tak
  zwraca 1000. Kolejne strony bierze się przez `startindex` — bez tego pobiera
  się w kółko tę samą stronę.

Jedna gmina (TERYT `120907`) zwraca każdy budynek ok. 120 razy: 13 673 wiersze
na 114 rzeczywistych budynków. To usterka jej powiatowej usługi, którą usługa
zbiorcza przepuszcza dalej. Skrypt odsiewa powtórzenia po geometrii, bo
`ID_BUDYNKU` i `gml_id` bywają dosłownie `None` i na klucz się nie nadają.
Żaden budynek tej gminy nie leży w korytarzu, więc wyników to nie dotyka.

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

Gdy pasujących plików jest **kilka** — co zdarza się po odświeżeniu danych, bo
stary komplet zostaje obok nowego — decyduje wiek danych, a nie kolejność
alfabetyczna. Bez tego wygrywałby `NOWE_PRG_PunktyAdresowe_12.shp` (litera `N`
przed `P`), czyli plik **starszy** od `PRG_PunktyAdresowe_12.shp`, i raport po
cichu liczyłby na nieaktualnych adresach. Skrypt wypisuje wtedy, które pliki
znalazł i który wybrał.

`./uruchom.sh --mode dane` pokazuje, który plik został wybrany, ile ma rekordów
i do kiedy sięgają dane (najnowsza sensowna data nadania adresu).

### Odświeżanie danych adresowych

Robi to [pobierz_prg.py](pobierz_prg.py):

```bash
.venv/bin/python pobierz_prg.py          # małopolskie
.venv/bin/python pobierz_prg.py --kod 14 # inne województwo
```

Nie da się tego zrobić prościej, bo GUGiK nie publikuje już paczek
wojewódzkich w SHP pod stałym adresem. Nazwy plików wewnątrz paczki zbiorczej
zawierają znacznik czasu generowania (`12_malopolskie_11.09.2026_11.35.23.gml`),
więc nie można ich adresować bezpośrednio — trzeba pobrać całą paczkę
ogólnopolską (ok. 755 MB) i wyciąć z niej województwo. Serwer nie obsługuje
żądań zakresowych, więc skrótu tu nie ma.

Paczka jest w **GML**, a nie SHP, i różni się układem: w SHP nazwa miejscowości
i ulicy stoi wprost przy punkcie adresowym, a w GML jest podlinkowana przez
`xlink:href` do osobnych obiektów `AD_Miejscowosc` i `AD_UlicaPlac`. Skrypt
czyta więc plik dwa razy — najpierw buduje słowniki, potem rozwiązuje odnośniki
przy punktach — i zapisuje wynik jako SHP o strukturze zgodnej z dotychczasową,
żeby reszta kodu nie wymagała zmian.

Jednej rzeczy w GML nie ma w ogóle: **nazwy gminy**, jest tylko kod TERYT.
Nazwy brane są z poprzedniej wersji pliku (kody w GML mają 7 cyfr, w SHP 6 —
ostatnia to rodzaj gminy), więc pierwsze uruchomienie wymaga, żeby stary plik
jeszcze leżał w `wojewodztwa-adresy/`.

### Źródło danych

Punkty adresowe pochodzą z **Państwowego Rejestru Granic (PRG)**, prowadzonego
przez Główny Urząd Geodezji i Kartografii (GUGiK):

<https://www.geoportal.gov.pl/pl/dane/panstwowy-rejestr-granic-prg/>

Zgodnie z informacją na Geoportalu dane PRG są udostępniane bezpłatnie
i do dowolnego wykorzystania. Wykorzystany zestaw to punkty adresowe
dla województwa małopolskiego (kod 12) — 866 938 rekordów, EPSG:2180.

Obrysy budynków pochodzą z **Ewidencji Gruntów i Budynków (EGiB)**, pobierane
zbiorczą usługą WFS GUGiK — szczegóły, warunki wykorzystania i podstawa prawna
w sekcji [Obrysy budynków (EGiB)](#obrysy-budynków-egib) wyżej:

<https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza>

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
- [pobierz_budynki.py](pobierz_budynki.py) — pobieranie obrysów budynków z EGiB
- [pobierz_prg.py](pobierz_prg.py) — odświeżanie punktów adresowych PRG
- [eksport_web.py](eksport_web.py) — dane dla mapy online
- [docs/](docs/) — strona na GitHub Pages
