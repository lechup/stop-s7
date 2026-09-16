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
./uruchom.sh --mode debug              # wykaz warstw w plikach wariantów
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

### Tunele

Odcinki tunelowe leżą w osobnej warstwie (`otrasyS7wtunelu_*`, `otrasyBDIwtunelu_*`)
i stanowią istotną część długości trasy w każdym z wariantów.

> Do wydania z listopada 2025 raport twierdził, że wariant E tuneli nie ma.
> Wynikało to z braku warstwy w plikach GML, których używaliśmy wcześniej —
> materiały źródłowe pokazują dla E 5,24 km odcinków tunelowych.

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
| `podsumowanie.csv` | wiersz na wariant: strefy, budynki, działki i tereny wrażliwe |
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
narastające `≤20 m` … `≤200 m`. Strefę rozstrzyga odległość do najbliższej
części korytarza, dokładnie jak przy adresach.

Siatka powtórzona jest **dwa razy**: z przedrostkiem `budynki` dla wszystkich
obiektów z EGiB i `budynki mieszkalne` dla `RODZAJ = 'm'`. Bez tego rozróżnienia
liczby w dalszych strefach są mylące — w pasie 50–200 m sporą część stanowią
stodoły, garaże i budynki gospodarcze, a pytanie brzmi zwykle „ilu ludzi to
dotyczy”, nie „ile obiektów stoi”.

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

### Szkoły, przychodnie i inne budynki użyteczności publicznej

EGiB klasyfikuje każdy budynek polem `RODZAJ` (atrybut `EGB_RodzajWgKST`).
Bez tego podziału szkoła i stodoła liczą się tak samo, dlatego obok
`budynki mieszkalne` raport wydziela dwie kategorie:

| kod | znaczenie | kolumna w raporcie |
|---|---|---|
| `m` | mieszkalny | `budynki mieszkalne` |
| `k` | oświaty, nauki i kultury oraz sportu | `budynki oświaty i sportu` |
| `z` | szpitala i inne budynki opieki zdrowotnej | `budynki opieki zdrowotnej` |
| `g` | produkcyjny, usługowy i gospodarczy | — |
| `t` | transportu i łączności | — |
| `b` | biurowy | — |
| `h` | handlowo-usługowy | — |
| `p` | przemysłowy | — |
| `s` | zbiornik, silos i budynek magazynowy | — |
| `i` | budynek niemieszkalny (reszta) | — |

Pełne oznaczenia:
[infografika GUGiK](https://www.gov.pl/web/zagospodarowanieprzestrzenne/infografika-oznaczenia-budynkow-egib-opis).
Mapa rozwija te skróty w dymkach — sama litera nic nie mówi. Kody spoza
klasyfikacji (w danych zdarza się `x`) pokazywane są wprost, bez zgadywania.

Uwaga dla pracujących na surowych danych: usługa WFS zapisuje braki jako
**literał `"None"`**, a nie pustą wartość. Dotyczy to zwłaszcza liczby
kondygnacji (ok. 3,3 tys. rekordów). `pobierz_budynki.py` zamienia je na
prawdziwe braki przy wczytaniu.

Obie kategorie liczone są w tej samej siatce stref co reszta. Rozkład:

| wariant | oświata: korytarz / ≤200 m | zdrowie: korytarz / ≤200 m |
|---|---|---|
| A | **1** / 2 | 0 / 1 |
| B | 0 / 1 | 0 / 0 |
| C | 0 / 6 | 0 / 0 |
| D | 0 / 9 | 0 / 1 |
| E | 0 / 9 | 0 / **8** |
| F | 0 / 4 | 0 / 0 |

Ten jeden budynek oświatowy w śladzie wariantu A to **Szkoła Podstawowa nr 1
im. Adama Mickiewicza w Świątnikach Górnych** (1331 m²). Leży w strefie
`nad tunelem`, więc jej los zależy od technologii drążenia — przy metodzie
odkrywkowej znika razem z resztą pasa.

Warto zestawić to z liczbą rozbiórek: wariant E wypada najlepiej pod względem
budynków w korytarzu (123), ale ma najwięcej obiektów oświatowych i zdrowotnych
w pasie 200 m.

**Czego EGiB nie powie.** Remizy OSP nie mają własnej klasy — trafiają do `i`
razem z szopami i wiatami, podobnie kościoły, poczty czy świetlice. Żeby je
wyodrębnić, trzeba drugiego źródła (OpenStreetMap albo BDOT10k, który ma funkcje
budynków i nazwy własne). Raport ich nie wskazuje i nie udaje, że potrafi.

### Mieszkania, a nie budynki — czego nie wiemy

Raport liczy **punkty adresowe i budynki**, nie gospodarstwa domowe. Blok
z pięćdziesięcioma mieszkaniami byłby tu jednym budynkiem i jednym adresem.
Sprawdziliśmy trzy możliwe źródła liczby mieszkań i żadne nie nadaje się do
użycia:

| źródło | dlaczego odpada |
|---|---|
| **NOBC** (rejestr TERYT, GUS) | formalnie obejmuje budynki *i mieszkania*, ale nie jest publiczny — bezpłatnie GUS udostępnia tylko TERC, SIMC i ULIC; NOBC wymaga wniosku, a dla podmiotów spoza wyłączeń ustawowych może być odpłatny |
| **bazy adresowe firm kurierskich** | własnościowe i niepublikowane, a przy tym pochodne od PRG/EMUiA — nie są niezależnym źródłem, a pobieranie ich łamałoby regulaminy i nie byłoby odtwarzalne |
| **OpenStreetMap** | ma właściwy tag `building:flats`, ale pokrycie jest znikome: **3 300 obiektów w całej Polsce**, a w korytarzu wariantu A dokładnie **2** (przy 1 164 adresach w OSM na tym obszarze) |

**W tych korytarzach to jednak nie ma znaczenia.** Wśród budynków mieszkalnych
w śladzie i nad tunelem nie ma ani jednego czterokondygnacyjnego w żadnym
wariancie; mediana powierzchni zabudowy to 108–123 m², a największy budynek
mieszkalny ma 399 m². To zabudowa jednorodzinna, więc przybliżenie „jeden
budynek ≈ jedno gospodarstwo domowe" się broni.

Gdyby trasa kiedyś dotknęła zabudowy wielorodzinnej, jedyne realne drogi to
pełny EGiB ze starostwa (ewidencja prowadzi lokale jako osobne obiekty; bezpłatna
jest tylko geometria z podstawowymi atrybutami) albo wniosek do GUS o NOBC.

### Działki i tereny wrażliwe

Poza adresami i budynkami raport podaje miary dotyczące **samej drogi**, a nie
tego, co przy niej stoi. Liczone są dla korytarza, czyli śladu razem z pasem
nad tunelem:

| kolumna | co znaczy |
|---|---|
| `działki` | ile działek ewidencyjnych przecina korytarz |
| `zajęte [ha]` | powierzchnia tych działek przypadająca na korytarz |
| `osuwiska [ha]` | ile korytarza przechodzi przez obszary osuwiskowe |
| `osuwisko aktywne ciągle [ha]` | z tego osuwiska czynne bez przerwy |
| `osuwisko aktywne okresowo [ha]` | czynne okresowo |
| `osuwisko nieaktywne [ha]` | nieczynne |
| `ruchy masowe [ha]` | obszary zagrożone ruchami masowymi ziemi |
| `tereny zalewowe [ha]` | tereny zagrożone powodzią |
| `obszary chronione [ha]` | obszary chronione przyrodniczo, łącznie |
| `park narodowy [ha]` i dalsze | rozbicie na dziesięć kategorii ochrony |

Osuwiska rozbite są na **czynne i nieczynne**, bo różnica jest kluczowa dla
kosztu i ryzyka budowy — osuwisko aktywne pod planowaną drogą to zupełnie inny
problem inżynieryjny niż ustabilizowane. Obszary chronione rozbite są na
dziesięć kategorii ochrony. Zera też zapisujemy: informacja, że **żaden wariant
nie tyka parku narodowego, rezerwatu ani obszaru Natura 2000**, jest sama
w sobie wynikiem i lepiej, żeby wynikała z tabeli niż z niczyjego zapewnienia.

Liczba działek jest istotna niezależnie od zabudowy: wywłaszczenie części
działki dotyka właściciela także wtedy, gdy nie stoi na niej dom. Osuwiska
i tereny zalewowe to z kolei argument inżynieryjny i kosztowy, a nie
mieszkaniowy — mówią, przez co droga ma przejść, a nie co zburzy.

Warstwy pochodzą z materiałów STEŚ. Działki są własne dla każdego wariantu
(przycięte do jego obszaru), pozostałe są wspólne i leżą w `warianty/kontekst.gpkg`
— są bajt w bajt identyczne we wszystkich wariantach, więc sześć kopii
kosztowałoby 255 MB nadmiaru.

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
  B                 100.9m           152.0m   50-200 m
  C                 691.4m           691.4m   poza 200 m
```

Kolumna `od powierzchni` liczona jest z pominięciem pasa nad tunelem, więc różnica
między nią a `od korytarza` pokazuje, że najbliżej przebiega odcinek tunelowy.

Tryb korzysta z zapisanych plików `wariant-X-slad.gpkg`, więc odpowiada od razu —
ale wymaga wcześniejszego przeliczenia (`./uruchom.sh`).

## Wiarygodność

Kontrola dotyczy kompletności danych adresowych: czy PRG nie gubi adresów,
których istnienie potwierdza niezależne źródło. Zestawienie z OpenStreetMap
dla korytarza wariantu A + 200 m:

| | liczba |
|---|---|
| adresy PRG | 1289 |
| adresy OSM | 1164 |
| OSM bez odpowiednika w PRG (15 m) | 32 (3%) |
| PRG bez odpowiednika w OSM (15 m) | 183 (14%) |

**PRG jest zbiorem szerszym, nie węższym** — zna 183 adresy nieobecne w OSM,
a brakuje mu 32 znanych OSM-owi. Gdyby systematycznie gubił adresy, proporcja
byłaby odwrotna. Te 32 to prawdopodobnie nowa zabudowa jeszcze nieujęta
w rejestrze albo błędy w OSM; przy 1289 adresach mówimy o wpływie rzędu 2%.

## Mapa online

Statyczna strona z mapą wariantów i wyszukiwarką adresu, wystawiana przez
GitHub Pages z katalogu [docs/](docs/):

<https://lechup.github.io/stop-s7/>

Wpisanie adresu pokazuje odległość i strefę we wszystkich wariantach naraz —
to odpowiednik trybu `--adres`, tyle że w przeglądarce. Budynki i adresy widać
we wszystkich strefach do 200 m, a każdą strefę da się osobno odkliknąć
(skróty `tylko ślad` i `wszystkie`), żeby odsiać tło i zobaczyć sam pas zajęcia
terenu.

Poza korytarzem, budynkami i adresami mapa pokazuje dwie warstwy terenowe:
**działki zajęte** (te przecinające korytarz, czyli dokładnie te, które raport
liczy) oraz cztery warstwy terenowe przycięte do 500 m od korytarza: **osuwiska**,
**obszary zagrożone ruchami mas**, **tereny zalewowe** i **obszary chronione**,
każda z osobnym przełącznikiem.

Obszary są podpisane rodzajem, bo rozróżnienie ma znaczenie merytoryczne:
osuwisko **aktywne ciągle** pod planowaną drogą to co innego niż nieaktywne,
a obszary chronione dzielą się na parki narodowe, rezerwaty, dwa typy Natury
2000 i kilka dalszych kategorii. Rodzaj siedzi w atrybucie `Layer` materiałów
źródłowych — pozostałe atrybuty są bezużyteczne (`EntityHand` to uchwyt obiektu
w DXF-ie, `Text` to nazwa wzoru kreskowania). Stały podpis dostają obszary
powyżej 5 ha; mniejszych jest ponad tysiąc i podpisanie każdego zamieniłoby mapę
w plątaninę, więc pokazują nazwę po najechaniu.
Obie są domyślnie wyłączone, a działki wczytują się dopiero po włączeniu —
ważą tyle co reszta wariantu razem wzięta, a do pytania „czy mój dom jest
zajęty" nie są potrzebne. Bez tego wejście na stronę kosztowałoby 460 kB
zamiast 216 kB, co na telefonie jest odczuwalne.

Budynki da się zawęzić w **dwóch wymiarach naraz** — po rodzaju z EGiB
i po liczbie kondygnacji nadziemnych. Dwie zwijane listy pod przełącznikiem
warstwy, z liczbą obiektów przy każdej pozycji i skrótami `wszystkie` / `żadne`.
Liczniki są fasetowe: lista rodzajów pokazuje liczby z uwzględnieniem stref
i filtra kondygnacji, ale nie samej siebie — inaczej odznaczenie pozycji
zerowałoby jej własną liczbę.

Filtr kondygnacji ma kubełki `1`, `2`, `3`, `4+` oraz dwa osobne na braki:
**`brak uprawnień`** i **`nieznana`**. To rozróżnienie jest istotne, bo znaczą
co innego — przy 17% budynków usługa WFS zwraca dosłowne `brak_uprawnień`
(atrybut istnieje, ale darmowy dostęp go nie obejmuje), a przy 37% wartości
po prostu nie ma. Razem daje to ponad połowę budynków bez użytecznej liczby
kondygnacji i strona mówi o tym wprost. Zaznaczyć można dowolną kombinację, a wybór działa
jednocześnie na mapę i na statystyki: można obejrzeć same domy mieszkalne,
albo mieszkalne razem z oświatą i opieką zdrowotną. Wybór przeżywa zmianę
wariantu.

Strona ma motyw jasny i ciemny. Domyślnie idzie **za ustawieniem systemu**
i reaguje na jego zmianę w locie; przycisk w nagłówku pozwala wybrać jawnie,
a wybór zapamiętuje `localStorage`. Kafelki OpenStreetMap są jasne, więc
w motywie ciemnym odwracamy je filtrem CSS — zamiast dokładać drugiego dostawcę
kafelków i kolejną politykę użytkowania.

Sekcja **„Korytarz przechodzi przez"** podaje miary terenowe dla całego
korytarza: liczbę działek, zajętą powierzchnię, osuwiska w rozbiciu na stopnie
aktywności, tereny zalewowe i obszary chronione. Te same liczby stoją przy
przełącznikach odpowiednich warstw. Pochodzą **wprost z `podsumowanie.csv`**,
więc mapa nie może pokazać czegoś innego niż raport — to ten sam wynik, a nie
drugie liczenie.

Miary terenowe są osobno od tabelki stref, bo mierzą co innego: strefy liczą
obiekty w sztukach i dotyczą otoczenia drogi, a te — hektary samego korytarza.

Przy każdej strefie stoi liczba adresów i budynków, a pod spodem suma tego, co
aktualnie widać na mapie — reagująca na odklikanie strefy, wybór rodzaju
budynku i wyłączenie całej warstwy. Liczby zgadzają się z `podsumowanie.csv`, więc tabelka w panelu jest
jednocześnie legendą i kontrolą. Widok zapisuje się
w adresie URL (`#C/17/49.9454/19.9742`), a po sprawdzeniu adresu dochodzi
piąty segment z samym adresem:

```
#A/17/49.9914/19.9833/Juliusza%20Osterwy%7C41P%7CKrak%C3%B3w
```

Otwarcie takiego linku odtwarza komplet: wypełnia pole wyszukiwania, stawia
znacznik i rozwija tabelkę z odległościami we wszystkich wariantach. Dzięki temu
udostępnia się nie „mapę gdzieś w okolicy", tylko konkretną odpowiedź na pytanie
„co z tym domem". Starsze linki bez tego segmentu działają jak dotąd, a gdy
adresu nie ma już w danych, strona mówi to wprost zamiast pokazać gołą mapę.

Do mapy dołączona jest strona [metoda.html](docs/metoda.html) —
„Jak to policzono i czego nie wiemy". Opisuje sposób odtworzenia śladu, obie
miary, granice danych i kontrole, z kotwicami przy sekcjach (`#kontrole`,
`#mieszkania`), żeby dało się podlinkować konkretny akapit w sporze o liczby.
Jest osobnym adresem, więc można ją podesłać bez mapy.

Dane generuje [eksport_web.py](eksport_web.py):

```bash
.venv/bin/python eksport_web.py
```

| plik | zawartość | po gzipie |
|---|---|---|
| `docs/dane/wariant-X.geojson` | korytarz, budynki i adresy jednego wariantu | 40–58 kB |
| `docs/dane/wariant-X-dzialki.geojson` | działki przecinające korytarz, wczytywane leniwie | 200–260 kB |
| `docs/dane/adresy-index.json` | 13 924 adresy z odległością do każdego wariantu | 362 kB |

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

### Statystyki odwiedzin

Strona liczy odwiedziny przez [GoatCounter](https://www.goatcounter.com/):

<https://stop-s7.goatcounter.com>

Wybrany świadomie zamiast Google Analytics: nie używa ciasteczek, nie zbiera
danych identyfikujących i według dokumentacji nie wymaga banera zgody — a przy
stronie, na którą ludzie wchodzą sprawdzić, czy stracą dom, wysyłanie ich ruchu
do Google byłoby kiepskim pomysłem.

Poza odsłonami liczone są zdarzenia:

| zdarzenie | kiedy |
|---|---|
| `wyszukiwanie` | zapytanie zwróciło trafienia |
| `wyszukiwanie-bez-wyniku` | zapytanie nic nie znalazło — dużo takich znaczy, że promień indeksu (500 m) jest za mały albo ludzie pytają spoza obszaru |
| `sprawdzenie-adresu` | ktoś kliknął wynik, czyli faktycznie sprawdził swój adres |
| `wariant-X` | świadome przełączenie wariantu (wczytanie strony się nie liczy) |
| `adres-z-linku` | ktoś wszedł z linku niosącego adres — miara tego, czy udostępnianie działa |
| `filtr-strefy` | zawężenie strefami |
| `filtr-rodzaje` | zawężenie rodzajem budynku |
| `filtr-warstwy` | przełączenie warstwy |

Zdarzenia zawężania i wyszukiwania są **zbiorcze**: ktoś odklikujący siedem
rodzajów budynków wykonuje jedną czynność, a nie siedem, i tak też się liczy.
Wpisanie „Osterwy" znak po znaku daje jedno zdarzenie, nie siedem — inaczej
statystyki mówiłyby więcej o zwinności palca niż o zachowaniu.

**Wysyłana jest wyłącznie nazwa zdarzenia.** Szukana fraza nigdy nie opuszcza
przeglądarki — to, czego ktoś szuka, jest informacją o tym, gdzie mieszka.

Domyślna ścieżka GoatCountera to `pathname + search`, więc hash ze stanem widoku
(`#A/17/49.9350/19.9607`) nie rozbija statystyk na tysiące osobnych „stron".

## Dane wejściowe

Katalogi `warianty/`, `wojewodztwa-adresy/` i `budynki/` nie są trzymane
w repozytorium — po rozpakowaniu zajmują ok. 790 MB. Leżą jako assety release'a
na GitHubie i pobiera je `pobierz_dane.py`:

| katalog | zawartość | archiwum |
|---|---|---|
| `warianty/` | warstwy wariantów A–F z materiałów STEŚ | `warianty-stes.tar.gz` (37 MB) |
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
ogólnopolską i wyciąć z niej województwo:

<https://opendata.geoportal.gov.pl/prg/adresy/PRG-punkty_adresowe.zip>

To ok. 755 MB. Serwer nie obsługuje
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

Przebiegi wariantów pochodzą z **materiałów konsultacyjnych STEŚ** (studium
techniczno-ekonomiczno-środowiskowe), wystawionych jako mapy przeglądowe —
po jednym serwisie na wariant:

| wariant | adres |
|---|---|
| A (W21/W18/W36) | <https://wariant-wa.s7-krakow-myslenice-stes.pl/> |
| B (W26/W21/W36) | <https://wariant-wb.s7-krakow-myslenice-stes.pl/> |
| C (W35/W16/W10) | <https://wariant-wc.s7-krakow-myslenice-stes.pl/> |
| D | <https://wariant-wd.s7-krakow-myslenice-stes.pl/> |
| E | <https://wariant-we.s7-krakow-myslenice-stes.pl/> |
| F | <https://wariant-wf.s7-krakow-myslenice-stes.pl/> |

Wydanie z **3 listopada 2025**, potwierdzone nagłówkiem `Last-Modified` serwisu.
Strony to eksporty qgis2web, w których każda warstwa jest plikiem JS z GeoJSON-em;
pobiera je [pobierz_warianty.py](pobierz_warianty.py). Stamtąd pochodzą nie tylko
osie i skarpy, ale też działki ewidencyjne, osuwiska, tereny zalewowe i obszary
chronione. Pełny inwentarz: [warstwy.md](warstwy.md).

**OpenStreetMap** służy do dwóch rzeczy: jest podkładem mapowym strony
([licencja ODbL](https://www.openstreetmap.org/copyright)) i niezależnym zbiorem odniesienia przy kontroli kompletności adresów, którą
odpytujemy przez [Overpass API](https://overpass-api.de/).

Mapa korzysta z biblioteki [Leaflet](https://leafletjs.com/) (BSD-2-Clause),
wczytywanej z CDN — nie jest kopiowana do repozytorium.

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

## Licencja

Kod: **[AGPLv3](LICENSE)** (GNU Affero General Public License v3).

Wybór padł na AGPL, a nie zwykłą GPL, z konkretnego powodu. Copyleft w GPL
uruchamia się przy *dystrybucji*, a ktoś, kto weźmie ten kod, po cichu zmieni
metodę — zawęzi ślad drogi, wytnie strefę nad tunelem — i postawi to pod swoim
adresem, niczego nie dystrybuuje. Świadczy usługę i pod GPL nie jest nikomu
winien ani linijki źródła. AGPL zamyka to w §13: kto udostępnia zmodyfikowaną
wersję przez sieć, musi udostępnić jej źródła użytkownikom tej strony.

Przy projekcie, którego cała wiarygodność stoi na odtwarzalności metody, to nie
jest niuans prawniczy. Inne inicjatywy walczące o swój odcinek drogi nadal mogą
wszystko wziąć i przerobić — pod warunkiem, że ich wersja też będzie jawna.

**Licencja obejmuje kod, nie dane.** Dane wejściowe mają własne warunki:

| co | źródło | warunki |
|---|---|---|
| punkty adresowe | PRG (GUGiK) | bezpłatnie, do dowolnego wykorzystania |
| obrysy budynków | EGiB (GUGiK) | geometria z podstawowymi atrybutami bezpłatnie, do dowolnego wykorzystania |
| warianty przebiegu | materiały konsultacji społecznych | — |

Wyliczone raporty (`podsumowanie.csv`, `rozbiorka.md`) powstały z danych
publicznych i można je cytować; przy powoływaniu się warto podać źródło
i rocznik danych, bo PRG aktualizowany jest na bieżąco.

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
