# Warstwy w plikach GML wariantów

Inwentarz wygenerowany z plików `warianty/wariant*.gml` (`pyogrio.list_layers`
+ `read_info`). Służy za podstawę wzorców w [consts.py](consts.py) — nazwy warstw
są niespójne między wariantami, więc dopasowujemy je regexem, a nie listą.

## Role i wzorce

| rola | wzorzec | do czego |
|---|---|---|
| `os` | `^otrasyS7_\d+(___2_)?$` | oś trasy S7 — cięcie na kafelki, metoda uproszczona |
| `os_bdi` | `^otrasyBDI_\d+(___2_)?$` | oś BDI (droga towarzysząca) — objęta tymi samymi warstwami krawędzi |
| `os_tunel` | `^otrasyS7wtunelu_\d+(___2_)?$` | odcinki w tunelu |
| `jezdnia` | `^pobocze_\d+(___2_)?$` | krawędzie jezdni — składnik śladu |
| `skarpy` | `^\d*(skarpy_)?part_[a-z]{2}(___2_)?$` | linie skarp — zewnętrzny obrys zajęcia terenu |
| `tunele` | `^projektowanetunele_\d+(___2_)?$` | poligony tuneli |
| `estakady` | `^projektowaneestakadyimosty_\d+(___2_)?$` | poligony estakad i mostów |
| `mop` | `^proponowanalokalizacjaMOP_\d+(___2_)?$` | proponowane lokalizacje MOP |
| `bufor200` | `^(otrasyS7_\d+|trasa)\.json$` | gotowy bufor 200 m od autorów materiałów — kontrola krzyżowa |
| `bufor500` | `^(otrasyS7_\d+|trasa)\.json___2_$` | gotowy bufor 500 m od autorów materiałów |

## Dopasowanie per wariant

| wariant | oś S7 | jezdnia | skarpy | tunele | bufor 200 m |
|---|---|---|---|---|---|
| A | 1 | 1 | 4 | 1 | 1 |
| B | 1 | 1 | **brak** | 1 | 1 |
| C | 1 | 1 | 3 | 1 | 1 |
| D | 1 | 1 | 4 | 1 | 1 |
| E | 1 | 1 | 4 | **brak** | 1 |
| F | 1 | 1 | 4 | 1 | 1 |

Wariant **B nie ma warstw skarp** — liczy się dla niego wyłącznie metodą
uproszczoną. Wariant **E nie ma tuneli**. Pozostałe mają komplet.

## Pełny wykaz

### Wariant A

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `otrasyBDI_15.json` | MultiPolygon | 4 | — |
| `otrasyS7_27.json` | MultiPolygon | 6 | `bufor200` |
| `otrasyBDI_15.json___2_` | MultiPolygon | 4 | — |
| `otrasyS7_27.json___2_` | MultiPolygon | 6 | `bufor500` |
| `otrasyS7_27___2_` | MultiLineString | 6 | `os` |
| `otrasyBDI_15___2_` | MultiLineString | 5 | `os_bdi` |
| `otrasyBDIwtunelu_14___2_` | MultiLineString | 2 | — |
| `otrasyS7wtunelu_26___2_` | MultiLineString | 5 | `os_tunel` |
| `projektowanetunele_20___2_` | MultiPolygon | 7 | `tunele` |
| `projektowaneestakadyimosty_21___2_` | MultiPolygon | 43 | `estakady` |
| `proponowanalokalizacjaMOP_16___2_` | MultiPolygon | 1 | `mop` |
| `proponowanyukaddrogowywzwdrogowych_18___2_` | MultiLineString | 60 | — |
| `schematizakresbudowylubprzebudowy_22___2_` | MultiLineString | 70 | — |
| `pobocze_25___2_` | MultiLineString | 10 | `jezdnia` |
| `part_aa___2_` | MultiLineString | 5000 | `skarpy` |
| `part_ab___2_` | MultiLineString | 5000 | `skarpy` |
| `part_ac___2_` | MultiLineString | 5000 | `skarpy` |
| `part_ad___2_` | MultiLineString | 1129 | `skarpy` |

### Wariant B

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `otrasyS7_27.json` | MultiPolygon | 6 | `bufor200` |
| `otrasyBDI_15.json` | MultiPolygon | 3 | — |
| `otrasyS7_27.json___2_` | MultiPolygon | 6 | `bufor500` |
| `otrasyBDI_15.json___2_` | MultiPolygon | 3 | — |
| `otrasyS7_27___2_` | MultiLineString | 14 | `os` |
| `otrasyS7wtunelu_26___2_` | MultiLineString | 6 | `os_tunel` |
| `otrasyBDI_15___2_` | MultiLineString | 4 | `os_bdi` |
| `otrasyBDIwtunelu_14___2_` | MultiLineString | 3 | — |
| `pobocze_25___2_` | MultiLineString | 28 | `jezdnia` |
| `projektowaneestakadyimosty_21___2_` | MultiPolygon | 34 | `estakady` |
| `projektowanetunele_20___2_` | MultiPolygon | 7 | `tunele` |

### Wariant C

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `otrasyBDI_15.json` | MultiPolygon | 4 | — |
| `otrasyS7_27.json` | MultiPolygon | 6 | `bufor200` |
| `otrasyBDI_15.json___2_` | MultiPolygon | 4 | — |
| `otrasyS7_27.json___2_` | MultiPolygon | 6 | `bufor500` |
| `otrasyS7_27___2_` | MultiLineString | 15 | `os` |
| `otrasyS7wtunelu_26___2_` | MultiLineString | 6 | `os_tunel` |
| `otrasyBDI_15___2_` | MultiLineString | 5 | `os_bdi` |
| `otrasyBDIwtunelu_14___2_` | MultiLineString | 4 | — |
| `pobocze_25___2_` | MultiLineString | 30 | `jezdnia` |
| `projektowaneestakadyimosty_21___2_` | MultiPolygon | 29 | `estakady` |
| `projektowanetunele_20___2_` | MultiPolygon | 8 | `tunele` |
| `proponowanalokalizacjaMOP_16___2_` | MultiPolygon | 2 | `mop` |
| `proponowanyukaddrogowywzwdrogowych_18___2_` | MultiLineString | 71 | — |
| `schematizakresbudowylubprzebudowy_22___2_` | MultiLineString | 67 | — |
| `skarpy_part_aa___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ab___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ac___2_` | MultiLineString | 3443 | `skarpy` |

### Wariant D

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `otrasyS7_24.json` | MultiPolygon | 1 | `bufor200` |
| `otrasyS7_24.json___2_` | MultiPolygon | 1 | `bufor500` |
| `otrasyS7_24___2_` | MultiLineString | 2 | `os` |
| `otrasyS7wtunelu_23___2_` | MultiLineString | 2 | `os_tunel` |
| `pobocze_22___2_` | MultiLineString | 26 | `jezdnia` |
| `projektowaneestakadyimosty_18___2_` | MultiPolygon | 32 | `estakady` |
| `projektowanetunele_17___2_` | MultiPolygon | 3 | `tunele` |
| `proponowanalokalizacjaMOP_14___2_` | MultiPolygon | 2 | `mop` |
| `proponowanyukaddrogowywzwdrogowych_16___2_` | MultiLineString | 60 | — |
| `schematizakresbudowylubprzebudowy_19___2_` | MultiLineString | 38 | — |
| `skarpy_part_aa___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ab___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ac___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ad___2_` | MultiLineString | 139 | `skarpy` |

### Wariant E

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `trasa.json` | MultiPolygon | 1 | `bufor200` |
| `trasa.json___2_` | MultiPolygon | 1 | `bufor500` |
| `proponowanalokalizacjaMOP_14` | MultiPolygon | 3 | `mop` |
| `otrasyS7_25` | MultiLineString | 1 | `os` |
| `pobocze_23` | MultiLineString | 12 | `jezdnia` |
| `schematizakresbudowylubprzebudowy_20` | MultiLineString | 33 | — |
| `proponowanyukaddrogowywzwdrogowych_17` | MultiLineString | 34 | — |
| `2part_aa` | MultiLineString | 5000 | `skarpy` |
| `part_ab` | MultiLineString | 5000 | `skarpy` |
| `part_ac` | MultiLineString | 5000 | `skarpy` |
| `part_ad` | MultiLineString | 4444 | `skarpy` |

### Wariant F

| warstwa | typ | obiektów | rola |
|---|---|---|---|
| `otrasyS7_24.json` | MultiPolygon | 1 | `bufor200` |
| `otrasyS7_24.json___2_` | MultiPolygon | 1 | `bufor500` |
| `otrasyS7_24___2_` | MultiLineString | 4 | `os` |
| `otrasyS7wtunelu_23___2_` | MultiLineString | 2 | `os_tunel` |
| `pobocze_22___2_` | MultiLineString | 6 | `jezdnia` |
| `projektowaneestakadyimosty_18___2_` | MultiPolygon | 34 | `estakady` |
| `projektowanetunele_17___2_` | MultiPolygon | 3 | `tunele` |
| `proponowanalokalizacjaMOP_14___2_` | MultiPolygon | 3 | `mop` |
| `proponowanyukaddrogowywzwdrogowych_16___2_` | MultiLineString | 53 | — |
| `schematizakresbudowylubprzebudowy_19___2_` | MultiLineString | 32 | — |
| `skarpy_part_aa___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ab___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ac___2_` | MultiLineString | 5000 | `skarpy` |
| `skarpy_part_ad___2_` | MultiLineString | 1215 | `skarpy` |

## Kalibracja promienia domknięcia

Ślad drogi powstaje z linii przez domknięcie morfologiczne
`buffer(+r).buffer(-r)`. Pomiar na kafelku 1×1 km w środku trasy wariantu A:

| r | pole | części | śr. szerokość |
|---|---|---|---|
| 15 m | 1,43 ha | 5 | 12,2 m |
| 20 m | 4,93 ha | 1 | 42,0 m |
| 25 m | 4,98 ha | 1 | 42,4 m |
| 30 m | 5,01 ha | 1 | 42,7 m |

Poniżej 20 m linie się nie domykają i ślad rozpada się na kawałki. Od 20 m
wynik wchodzi na płaskowyż, więc `PROMIEN_DOMKNIECIA = 25` leży w środku
stabilnego zakresu i nie jest wrażliwy na dobór wartości.

Warstwa `schematizakresbudowylubprzebudowy_*` mimo obiecującej nazwy **nie
daje się `polygonize`** (0 poligonów) — nie jest gotowym obrysem zajęcia terenu.

