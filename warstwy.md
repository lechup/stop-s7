# Warstwy w plikach wariantów

Dane pochodzą z serwisów konsultacyjnych STEŚ (`wariant-w*.s7-krakow-myslenice-stes.pl`),
wydanie z **3 listopada 2025** (potwierdzone nagłówkiem `Last-Modified`).
Pobiera je i składa [pobierz_warianty.py](pobierz_warianty.py).

Nazwa warstwy w GPKG **jest** jej rolą — w przeciwieństwie do wcześniejszych
plików GML, gdzie numeracja i sufiksy różniły się między wariantami i trzeba
je było dopasowywać wzorcem.

## Warstwy własne wariantu

Plik `warianty/wariant-X.gpkg`.

| warstwa | A | B | C | D | E | F | rola |
|---|---|---|---|---|---|---|---|
| `dzialki` | 7871 | 7599 | 8386 | 7856 | 10353 | 12894 | **miara** — działki ewidencyjne |
| `estakady` | 43 | 34 | 29 | 32 | 18 | 34 | **składnik śladu** — estakady i mosty |
| `jezdnia` | 10 | 28 | 30 | 26 | 12 | 6 | **składnik śladu** — krawędzie pobocza |
| `kilometraz_100m` | 298 | 296 | 287 | 263 | 285 | 293 | kilometraż co 100 m |
| `kilometraz_1km` | 31 | 30 | 29 | 27 | 29 | 30 | kilometraż co 1 km |
| `krawedzie` | 20 | 54 | 60 | 30 | 21 | 12 | krawędzie jezdni |
| `mop` | 1 | 2 | 2 | 2 | 3 | 3 | proponowane MOP-y |
| `nazwy_wezlow` | 6 | 6 | 6 | 4 | 7 | 5 | nazwy węzłów |
| `os` | 6 | 14 | 15 | 2 | 1 | 4 | oś trasy S7 |
| `os_bdi` | 5 | 4 | 5 | — | — | — | oś drogi towarzyszącej |
| `os_tunel` | 5 | 6 | 6 | 2 | 1 | 2 | odcinki tunelowe S7 |
| `os_tunel_bdi` | 2 | 3 | 4 | — | — | — | odcinki tunelowe BDI |
| `skarpy` | 16129 | 14401 | 13443 | 15139 | 19444 | 16215 | **składnik śladu** — linie skarp |
| `tunele` | 7 | 7 | 8 | 3 | 2 | 3 | poligony tuneli |
| `uklad_wezlow` | 60 | 49 | 71 | 61 | 34 | 53 | **miara** — łącznice węzłów |
| `wezly` | 5 | 5 | 5 | — | — | — | symbol węzła (okrąg r = 100 m), nie obrys |
| `zakres_budowy` | 72 | 78 | 74 | 47 | 38 | 45 | schemat zakresu budowy |

## Warstwy wspólne

Plik `warianty/kontekst.gpkg`. Są **bajt w bajt identyczne** we wszystkich
wariantach — sprawdzone sumami sha256 pobranych plików — więc trzymanie ich
w sześciu kopiach kosztowałoby 255 MB nadmiaru.

| warstwa | obiektów | rola |
|---|---|---|
| `chronione` | 13 | **miara** — obszary chronione przyrodniczo |
| `gminy` | 32 | granice gmin |
| `obreby` | 686 | granice obrębów ewidencyjnych |
| `osuwiska` | 3 | **miara** — obszary osuwiskowe |
| `pomniki_przyrody` | 7616 | pomniki przyrody |
| `powiaty` | 4 | granice powiatów |
| `powodz` | 5 | **miara** — tereny zalewowe |
| `ruchy_masowe` | 1 | **miara** — zagrożenie ruchami masowymi |
| `s52` | 20088 | przebieg S52 |

## Węzły: łącznice są kreską, nie powierzchnią

Warstwy budujące ślad (`jezdnia` — w CAD-zie `D-Plan-Pobocze`, `skarpy`,
`krawedzie`) opisują **wyłącznie trasę główną**. W wariancie A `jezdnia` to
cztery równoległe linie ciągnące się przez całe 12 km i żadna z nich się nie
rozgałęzia. Domknięcie morfologiczne wypełnia teren *między* liniami pobocza,
więc przy węźle nie ma czego domykać — ze śladu zostają tam same poligony
estakad (`M-Plan-EstakadaHatch`), stąd wrażenie, że ślimaki gdzieś zniknęły.

Łącznice są w danych, tylko w warstwie `uklad_wezlow` (`D-Plan-SchematyWezlow`)
i **narysowane samą kreską** — bez pary linii pobocza i bez skarp. Że to
geometria w terenie, a nie rysunek poglądowy obok arkusza, widać po rozkładzie:
w wariancie A 99% z 16,9 km tych linii leży w promieniu 600 m od nazwanych
węzłów, odsuwając się od osi trasy najdalej o 490 m.

Ponieważ szerokości nie da się odczytać z rysunku, przyjmujemy ją: **8 m od
kreski w każdą stronę** (`consts.SZEROKOSC_LACZNICY`), tyle co jednopasowa
łącznica z poboczami. To jedyne założenie w całym wyliczeniu, dlatego łącznice
**nie wchodzą do śladu drogi** i liczą się w osobnych kolumnach. Skala pominięcia
w wariancie A: 15,6 ha poza dotychczasowym korytarzem (+10% jego powierzchni),
a w tym pasie 11 adresów, 17 budynków i 326 działek. Przy ±5 m byłoby to 10,3 ha,
przy ±12 m — 22,5 ha.

Osobna pułapka: warstwa `wezly` wygląda na obrys węzła, a to pięć **identycznych
okręgów o promieniu 100 m** (3,1350 ha każdy, kolistość 1,000) — symbole
lokalizujące węzeł na planie. Do żadnej miary nie wchodzą.

Część węzłów nie ma linii łącznic w ogóle (w wariancie A: Myślenice Północ
i Głogoczów) — to prawdopodobnie węzły istniejące, nieprzebudowywane.

## Kalibracja śladu

Ślad drogi składany jest z warstw `jezdnia`, `skarpy` i `estakady`.
Pierwsze dwie to linie i łączy je domknięcie morfologiczne o promieniu
**25 m**; poniżej 20 m linie skarp się nie domykają i ślad rozpada się na
kawałki, a od 20 m wynik wchodzi na płaskowyż.

Estakady są już poligonami i dochodzą wprost. Bez nich ślad miałby dziury:
tam, gdzie droga idzie po estakadzie, nie ma nasypu, więc nie ma i linii
skarp — a budynek pod projektowaną estakadą jest zajęty tak samo.

