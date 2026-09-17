"""Zliczanie punktow adresowych wzgledem sladu drogi."""

import glob
import os
import re

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely

import consts
import geometria

KATALOG_ADRESOW = "wojewodztwa-adresy"
WZORZEC_ADRESOW = "*PunktyAdresowe*.shp"

_plik_adresow = None


def znajdz_plik_adresow():
  """Znajduje plik z punktami adresowymi, rozpoznajac go po zawartosci.

  Nie mozna polegac na nazwie. GUGiK od 1 lipca 2026 publikuje dane adresowe
  tylko w nowej strukturze i przy tej okazji usunal prefiks "NOWE_" — plik
  nazywa sie teraz PRG_PunktyAdresowe_*, ale dokladnie taka nazwe nosila
  wczesniej STARA struktura, o zupelnie innych polach (Numer, ULIC_nazwa,
  SIMC_nazwa zamiast NUMER_PORZ, NAZWA_ULC, NAZWA_MSC). Sama nazwa nie mowi
  wiec nic — decyduje obecnosc wymaganych kolumn."""
  global _plik_adresow
  if _plik_adresow:
    return _plik_adresow

  kandydaci = sorted(glob.glob(
      os.path.join(KATALOG_ADRESOW, "**", WZORZEC_ADRESOW), recursive=True))
  if not kandydaci:
    raise SystemExit(
        "Nie znalazlem pliku z punktami adresowymi ({}/**/{}).\n"
        "Pobierz dane: python3 pobierz_dane.py".format(
            KATALOG_ADRESOW, WZORZEC_ADRESOW))

  odrzucone = []
  pasujace = []
  for sciezka in kandydaci:
    try:
      pola = set(pyogrio.read_info(sciezka)["fields"])
    except Exception as blad:
      odrzucone.append((sciezka, str(blad)[:50]))
      continue
    brakuje = [k for k in KOLUMNY if k not in pola]
    if brakuje:
      odrzucone.append((sciezka, "brak pol: " + ", ".join(brakuje)))
      continue
    pasujace.append(sciezka)

  if len(pasujace) == 1:
    _plik_adresow = pasujace[0]
    return _plik_adresow

  if len(pasujace) > 1:
    # Po odswiezeniu danych w katalogu potrafi zostac stary plik obok nowego —
    # obydwa maja wymagane kolumny, wiec sama struktura ich nie rozroznia.
    # Wybor alfabetyczny cichaczem wskazalby "NOWE_PRG_..." (dane z grudnia)
    # zamiast "PRG_..." (wrzesniowe), dlatego decyduje wiek danych.
    wiek = [(najnowsza_data(s), s) for s in pasujace]
    wiek.sort(key=lambda para: (para[0] is not None, para[0]))
    _plik_adresow = wiek[-1][1]
    print("Uwaga: {} pliki z adresami maja wymagane kolumny. Biore najnowszy:".format(
        len(pasujace)))
    for data, sciezka in reversed(wiek):
      print("  {} {} (stan {})".format(
          "->" if sciezka == _plik_adresow else "  ", sciezka,
          data.strftime("%d.%m.%Y") if data else "nieustalony"))
    return _plik_adresow

  raise SystemExit(
      "Znalazlem pliki z adresami, ale zaden nie ma wymaganych pol ({}).\n"
      "{}\n"
      "Prawdopodobnie to dane w starej strukturze, wycofanej przez GUGiK\n"
      "1 lipca 2026. Pobierz aktualny pakiet PRG.".format(
          ", ".join(KOLUMNY),
          "\n".join("  {} — {}".format(p, d) for p, d in odrzucone)))
KOLUMNY = ["NUMER_PORZ", "NAZWA_ULC", "NAZWA_MSC", "NAZWA_GMI", "KOD_POCZT"]
KATALOG_WYNIKOW = "raporty"

# Powyzej tylu trafien --adres skraca wydruk do jednej linii na adres.
SZCZEGOLOWO_DO = 5

W_SLADZIE = "w śladzie"
NAD_TUNELEM = "nad tunelem"
DO_ROZBIORKI = "do rozbiórki"
BUDYNKI = "budynki"
BUDYNKI_MIESZKALNE = "budynki mieszkalne"
BUDYNKI_OSWIATA = "budynki oświaty i sportu"
BUDYNKI_ZDROWIE = "budynki opieki zdrowotnej"

PLIK_BUDYNKOW = "budynki/budynki.gpkg"

# Rodzaj budynku wg KST w EGiB (atrybut EGB_RodzajWgKST):
#   m mieszkalny            g produkcyjny, uslugowy i gospodarczy
#   t transportu i lacznosci  k oswiaty, nauki i kultury oraz sportu
#   z szpitala i opieki zdrowotnej   b biurowy      h handlowo-uslugowy
#   p przemyslowy           s zbiornik, silos, magazyn   i niemieszkalny
# https://www.gov.pl/web/zagospodarowanieprzestrzenne/infografika-oznaczenia-budynkow-egib-opis
RODZAJ_MIESZKALNY = "m"
# Wyodrebnione osobno, bo szkola albo przychodnia w sladzie to co innego niz
# stodola — a bez tego podzialu obie znikaly we wspolnej liczbie "budynki".
# OSP, kosciolow czy poczty EGiB nie rozroznia: ida do "i" razem z szopami.
RODZAJ_OSWIATA = "k"
RODZAJ_ZDROWIE = "z"

# Nazwy warstw w wariant-X-slad.gpkg. Korytarz musi byc adresowany po nazwie,
# bo od kiedy plik ma kilka warstw, odczyt bez wskazania warstwy siegnalby
# po pierwsza z brzegu.
WARSTWA_KORYTARZ = "korytarz"
WARSTWA_BUDYNKI = "budynki"
WARSTWA_ADRESY = "adresy"
WARSTWA_LACZNIC = "lacznice"

_budynki_cache = None
_budynki_sprawdzone = False


def wczytaj_budynki():
  """Obrysy budynkow z EGiB albo None, jesli ich nie pobrano.

  Budynki sa opcjonalne: bez nich raport liczy sie jak dotad, tylko bez kolumn
  budynkowych. Pobiera je pobierz_dane.py razem z reszta albo pobierz_budynki.py."""
  global _budynki_cache, _budynki_sprawdzone
  if not _budynki_sprawdzone:
    _budynki_sprawdzone = True
    if os.path.exists(PLIK_BUDYNKOW):
      _budynki_cache = gpd.read_file(PLIK_BUDYNKOW).to_crs(consts.CRS_METRYCZNY)
  return _budynki_cache


def trafione_budynki(warstwy):
  """Budynki do najdalszej strefy od korytarza, ze strefa i odlegloscia.

  Liczone tak samo jak adresy, zeby obie miary dalo sie zestawiac: przeciecie
  ze sladem to "w sladzie", przeciecie z pasem tunelu to "nad tunelem",
  a poza nimi decyduje odleglosc do najblizszej czesci korytarza.

  Przeciecie, a nie zawieranie: budynek stojacy w sladzie polowa i tak trafia
  w pas zajecia terenu. Zwraca None, gdy nie ma danych o budynkach."""
  budynki = wczytaj_budynki()
  if budynki is None:
    return None

  korytarz = warstwy["korytarz"]
  czesci = gpd.GeoDataFrame(
      geometry=list(shapely.get_parts(korytarz)), crs=consts.CRS_METRYCZNY)
  pary = gpd.sjoin_nearest(
      budynki, czesci, max_distance=float(max(consts.STREFY)),
      distance_col="odleglosc_m", how="inner")
  if pary.empty:
    return budynki.iloc[0:0].assign(odleglosc_m=[], strefa=[])

  # sjoin_nearest zwraca wiersz na kazda remisujaca czesc korytarza.
  pary = pary.sort_values("odleglosc_m").groupby(level=0).first()
  trafione = budynki.loc[pary.index].copy()
  trafione["odleglosc_m"] = pary["odleglosc_m"].round(1)

  w_sladzie = set(budynki.sindex.query(
      warstwy["powierzchnia"], predicate="intersects"))
  nad_tunelem = set()
  if warstwy.get("tunel") is not None:
    nad_tunelem = set(budynki.sindex.query(
        warstwy["tunel"], predicate="intersects")) - w_sladzie

  pozycje = {idx: i for i, idx in enumerate(budynki.index)}
  strefy = []
  for idx, odleglosc in zip(trafione.index, trafione["odleglosc_m"]):
    pozycja = pozycje[idx]
    if pozycja in w_sladzie:
      strefy.append(W_SLADZIE)
    elif pozycja in nad_tunelem:
      strefy.append(NAD_TUNELEM)
    else:
      strefy.append(_strefa(odleglosc) or nazwy_stref()[2])
  trafione["strefa"] = strefy
  return trafione.reset_index(drop=True)


def wczytaj_adresy(obszar):
  """Czyta tylko adresy z otoczenia obszaru.

  Plik ma 856 tys. rekordow i 786 MB atrybutow — wczytywanie calosci jest
  zbedne i kosztuje kilka GB, wiec filtrujemy bbox-em juz przy odczycie."""
  minx, miny, maxx, maxy = shapely.bounds(obszar)
  m = max(consts.STREFY)
  gdf = gpd.read_file(
      znajdz_plik_adresow(),
      bbox=(minx - m, miny - m, maxx + m, maxy + m),
      columns=KOLUMNY,
  )
  # Shapefile podaje uklad jako WKT ("ETRF2000-PL / CS92"), a nasze geometrie
  # maja go jako EPSG:2180. To ten sam uklad, ale bez ujednolicenia geopandas
  # zglasza niezgodnosc CRS przy zlaczeniach przestrzennych.
  return gdf.to_crs(consts.CRS_METRYCZNY)


def stan_danych():
  """Najnowsza sensowna data nadania adresu — czyli do kiedy siegaja dane.

  Pole DATA_NAD zawiera w zrodle bledne wpisy (daty w rodzaju 0203 albo 2984),
  wiec odsiewamy wartosci poza realnym zakresem. Zwraca None, jesli pliku nie
  da sie odczytac albo nie ma takiego pola."""
  return najnowsza_data(znajdz_plik_adresow())


def najnowsza_data(sciezka):
  """Najnowsza sensowna data nadania adresu w danym pliku (None, gdy sie nie da)."""
  try:
    dane = pyogrio.read_dataframe(
        sciezka, columns=["DATA_NAD"], read_geometry=False)
  except Exception:
    return None
  if "DATA_NAD" not in dane:
    return None
  daty = pd.to_datetime(dane["DATA_NAD"], errors="coerce")
  daty = daty[(daty >= "1950-01-01") & (daty <= pd.Timestamp.today())]
  return daty.max().date() if len(daty) else None


def nazwy_stref():
  """Nazwy stref rozlacznych, od sladu na zewnatrz."""
  nazwy = [W_SLADZIE, NAD_TUNELEM]
  poprzedni = 0
  for prog in consts.STREFY:
    nazwy.append("{}-{} m".format(poprzedni, prog))
    poprzedni = prog
  return nazwy


def _strefa(odleglosc):
  poprzedni = 0
  for prog in consts.STREFY:
    if odleglosc <= prog:
      return "{}-{} m".format(poprzedni, prog)
    poprzedni = prog
  return None


def policz(wariant, postep=None):
  """Liczy rozklad adresow wzgledem korytarza drogi.

  Korytarz dzieli sie na dwie czesci liczone osobno:
    - slad powierzchniowy — droga na powierzchni,
    - pas nad tunelem — teren rozkopany, jesli tunel budowany jest odkrywkowo.
  Metoda dokladna sama z siebie zostawia nad tunelem dziure (nie ma tam linii
  skarp), a uproszczona buforuje os takze pod tunelem — rozdzielenie sprowadza
  obie metody do tej samej definicji.

  Zwraca (GeoDataFrame adresow, warstwy korytarza)."""
  nazwy = geometria.nazwy_warstw(wariant)
  slad_pelny = geometria.slad_drogi(wariant, postep)
  if slad_pelny is None:
    return None, None

  pas = geometria.pas_tunelu(wariant, nazwy)
  if pas is None:
    powierzchnia, korytarz = slad_pelny, slad_pelny
  else:
    powierzchnia = shapely.difference(slad_pelny, pas)
    korytarz = shapely.union_all([slad_pelny, pas])

  warstwy = {"powierzchnia": powierzchnia, "tunel": pas,
             "korytarz": korytarz,
             "lacznice": geometria.lacznice(wariant, nazwy)}

  adresy = wczytaj_adresy(korytarz)
  if adresy.empty:
    return adresy.assign(odleglosc_m=[], strefa=[]), warstwy

  # Odleglosc liczymy do poszczegolnych czesci korytarza, nie do calosci —
  # drzewo STR odsiewa wtedy dalekie czesci zamiast porownywac kazdy punkt
  # z cala, skomplikowana geometria.
  czesci = gpd.GeoDataFrame(
      geometry=list(shapely.get_parts(korytarz)), crs=consts.CRS_METRYCZNY)

  pary = gpd.sjoin_nearest(
      adresy, czesci, max_distance=float(max(consts.STREFY)),
      distance_col="odleglosc_m", how="inner")
  if pary.empty:
    return adresy.iloc[0:0].assign(odleglosc_m=[], strefa=[]), warstwy

  # sjoin_nearest zwraca po wierszu na kazda remisujaca czesc korytarza.
  pary = pary.sort_values("odleglosc_m").groupby(level=0).first()
  wynik = adresy.loc[pary.index].copy()
  wynik["odleglosc_m"] = pary["odleglosc_m"].round(1)

  w_sladzie = set(adresy.sindex.query(powierzchnia, predicate="contains"))
  nad_tunelem = set()
  if pas is not None:
    nad_tunelem = set(adresy.sindex.query(pas, predicate="contains")) - w_sladzie

  pozycje = {idx: i for i, idx in enumerate(adresy.index)}
  strefy = []
  for idx, odl in zip(wynik.index, wynik["odleglosc_m"]):
    poz = pozycje[idx]
    if poz in w_sladzie:
      strefy.append(W_SLADZIE)
    elif poz in nad_tunelem:
      strefy.append(NAD_TUNELEM)
    else:
      # Punkt tuz przy krawedzi moze miec odleglosc 0 i nie byc "wewnatrz".
      strefy.append(_strefa(odl) or nazwy_stref()[2])
  wynik["strefa"] = strefy
  return wynik, warstwy


def _dopisz_strefy(wiersz, przedrostek, strefy):
  """Komplet kolumn dla jednej miary: strefy rozlaczne, suma dla korytarza
  i kolumny narastajace. Uzywane osobno dla wszystkich budynkow i dla samych
  mieszkalnych, zeby obie dalo sie czytac w tej samej siatce co adresy."""
  liczby = strefy.value_counts() if len(strefy) else {}
  for nazwa in nazwy_stref():
    wiersz["{} {}".format(przedrostek, nazwa)] = int(liczby.get(nazwa, 0))

  wiersz[przedrostek] = (wiersz["{} {}".format(przedrostek, W_SLADZIE)]
                         + wiersz["{} {}".format(przedrostek, NAD_TUNELEM)])

  narastajaco = wiersz[przedrostek]
  poprzedni = 0
  for prog in consts.STREFY:
    narastajaco += wiersz["{} {}-{} m".format(przedrostek, poprzedni, prog)]
    wiersz["{} ≤{} m".format(przedrostek, prog)] = narastajaco
    poprzedni = prog


# Warstwy terenowe: nazwa warstwy w GPKG -> nazwa kolumny w podsumowaniu.
# Wszystkie sa poligonowe i liczymy dla nich POWIERZCHNIE korytarza, ktora na
# nie przypada — inaczej niz przy adresach i budynkach, gdzie liczymy obiekty.
# Osuwiska, tereny zalewowe i obszary chronione to nie jest "co zostanie
# zburzone", tylko "przez co droga ma przejsc".
WARSTWY_TERENU = {
    "osuwiska": "osuwiska [ha]",
    "ruchy_masowe": "ruchy masowe [ha]",
    "powodz": "tereny zalewowe [ha]",
    "chronione": "obszary chronione [ha]",
}
PLIK_KONTEKSTU = "warianty/kontekst.gpkg"

_kontekst = {}


# Warstwy, dla ktorych podajemy rozbicie na rodzaje. Przy osuwiskach roznica
# miedzy czynnym a nieczynnym jest kluczowa dla kosztu i ryzyka budowy, przy
# obszarach chronionych — dla tego, czy droga w ogole moze tamtedy przejsc.
WARSTWY_Z_RODZAJAMI = {"osuwiska": "osuwiska", "chronione": "obszary chronione"}

_rodzaje = {}


def rodzaje_kontekstu(warstwa):
  """Obszary warstwy pogrupowane po rodzaju: {nazwa rodzaju: geometria}.

  Rodzaj siedzi w atrybucie Layer materialow zrodlowych."""
  if warstwa not in _rodzaje:
    wynik = {}
    try:
      gdf = gpd.read_file(PLIK_KONTEKSTU, layer=warstwa).to_crs(consts.CRS_METRYCZNY)
      gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
      domyslna = WARSTWY_Z_RODZAJAMI.get(warstwa, warstwa)
      gdf["_rodzaj"] = [consts.nazwa_rodzaju(v, domyslna)
                        for v in gdf.get("Layer", [None] * len(gdf))]
      for rodzaj, grupa in gdf.groupby("_rodzaj"):
        wynik[rodzaj] = shapely.union_all(grupa.geometry.values)
    except Exception:
      pass
    _rodzaje[warstwa] = wynik
  return _rodzaje[warstwa]


def wczytaj_kontekst(warstwa):
  """Warstwa terenowa wspolna dla wszystkich wariantow (None, gdy jej nie ma).

  Trzymana w jednym pliku, bo jest identyczna we wszystkich wariantach —
  szesc kopii kosztowaloby 255 MB nadmiaru."""
  if warstwa not in _kontekst:
    try:
      gdf = gpd.read_file(PLIK_KONTEKSTU, layer=warstwa).to_crs(consts.CRS_METRYCZNY)
      _kontekst[warstwa] = shapely.union_all(shapely.make_valid(gdf.geometry.values))
    except Exception:
      _kontekst[warstwa] = None
  return _kontekst[warstwa]


# Progi dotkliwosci zajecia dzialki [%]. Dzialka tracaca 3% to co innego niz
# tracaca 80% — ta druga przestaje sie nadawac do czegokolwiek, a w samej
# liczbie dzialek obie wazyly tyle samo.
PROGI_ZAJECIA = [50, 90]


def zajete_dzialki(wariant, korytarz):
  """Dzialki przeciete przez korytarz, z udzialem zajecia i informacja o zabudowie.

  Zwraca GeoDataFrame z kolumnami udzial_proc i zabudowana."""
  try:
    dzialki = gpd.read_file(geometria.sciezka(wariant), layer="dzialki")
  except Exception:
    return None
  dzialki = dzialki.to_crs(consts.CRS_METRYCZNY)
  dzialki["geometry"] = shapely.make_valid(dzialki.geometry.values)
  trafione = dzialki.iloc[sorted(set(
      dzialki.sindex.query(korytarz, predicate="intersects")))].copy()
  if trafione.empty:
    return trafione

  pola = trafione["pow_m2"].astype(float)
  zajete = shapely.area(shapely.intersection(trafione.geometry.values, korytarz))
  trafione["zajete_m2"] = zajete
  trafione["udzial_proc"] = [
      round(100 * z / p, 1) if p else 0.0 for z, p in zip(zajete, pola)]

  budynki = wczytaj_budynki()
  zabudowane = set()
  if budynki is not None and len(budynki):
    pary = budynki.sindex.query(trafione.geometry.values, predicate="intersects")
    zabudowane = set(pary[0].tolist())
  trafione["zabudowana"] = [i in zabudowane for i in range(len(trafione))]
  return trafione


def miary_lacznic(wariant, korytarz, pas):
  """Ile terenu dokladaja lacznice wezlow poza sladem drogi.

  Kolumny sa osobne, a nie doliczone do sladu, bo szerokosc lacznic jest
  zalozona (consts.SZEROKOSC_LACZNICY), podczas gdy caly slad wynika wprost
  z narysowanych linii. Bez tej miary zajecie terenu przy wezlach wychodzi
  zanizone — w materialach lacznice sa tylko kreska, wiec do sladu nie wnosza
  nic poza poligonami estakad."""
  if pas is None or shapely.is_empty(pas):
    return {}
  nowe = shapely.difference(pas, korytarz)
  wynik = {"łącznice [ha]": round(shapely.area(nowe) / 10000, 1)}
  if shapely.is_empty(nowe):
    return wynik

  adresy = wczytaj_adresy(nowe)
  if len(adresy):
    wynik["adresy w łącznicach"] = len(set(
        adresy.sindex.query(nowe, predicate="intersects").tolist()))

  budynki = wczytaj_budynki()
  if budynki is not None and len(budynki):
    wynik["budynki w łącznicach"] = len(set(
        budynki.sindex.query(nowe, predicate="intersects").tolist()))

  trafione = zajete_dzialki(wariant, nowe)
  if trafione is not None:
    wynik["działki w łącznicach"] = len(trafione)
  return wynik


def miary_terenu(wariant, korytarz):
  """Ile korytarza przypada na dzialki ewidencyjne i tereny wrazliwe.

  Dzialki sa wlasne dla wariantu (przyciete do jego obszaru), reszta wspolna."""
  wynik = {}

  trafione = zajete_dzialki(wariant, korytarz)
  if trafione is not None and len(trafione):
    wynik["działki"] = len(trafione)
    wynik["zajęte [ha]"] = round(trafione["zajete_m2"].sum() / 10000, 1)
    wynik["działki zabudowane"] = int(trafione["zabudowana"].sum())
    wynik["działki niezabudowane"] = int((~trafione["zabudowana"]).sum())
    for prog in PROGI_ZAJECIA:
      wynik["działki zajęte >{}%".format(prog)] = int(
          (trafione["udzial_proc"] > prog).sum())

  for warstwa, kolumna in WARSTWY_TERENU.items():
    obszar = wczytaj_kontekst(warstwa)
    if obszar is None:
      continue
    wynik[kolumna] = round(
        shapely.area(shapely.intersection(korytarz, obszar)) / 10000, 1)

    # Rozbicie na rodzaje. Zera tez zapisujemy — informacja, ze zaden wariant
    # nie tyka parku narodowego ani Natury 2000, jest sama w sobie wynikiem.
    if warstwa in WARSTWY_Z_RODZAJAMI:
      for rodzaj, geometria_rodzaju in sorted(rodzaje_kontekstu(warstwa).items()):
        wynik["{} [ha]".format(rodzaj)] = round(
            shapely.area(shapely.intersection(korytarz, geometria_rodzaju)) / 10000, 1)
  return wynik


def podsumuj(wariant, adresy, budynki=None, teren=None):
  """Wiersz podsumowania: strefy rozlaczne + kolumny narastajace.

  Budynki dostaja te sama siatke stref co adresy — osobno wszystkie, osobno
  mieszkalne — zeby dalo sie je zestawiac wprost. To NIEZALEZNE miary, a nie
  poprawka jedna do drugiej: jeden budynek miewa kilka adresow albo zaden,
  a EGiB obejmuje takze garaze i budynki gospodarcze."""
  wiersz = {"wariant": wariant}
  liczby = adresy["strefa"].value_counts() if len(adresy) else {}
  for nazwa in nazwy_stref():
    wiersz[nazwa] = int(liczby.get(nazwa, 0)) if len(adresy) else 0

  wiersz[DO_ROZBIORKI] = wiersz[W_SLADZIE] + wiersz[NAD_TUNELEM]

  narastajaco = wiersz[DO_ROZBIORKI]
  poprzedni = 0
  for prog in consts.STREFY:
    narastajaco += wiersz["{}-{} m".format(poprzedni, prog)]
    wiersz["≤{} m".format(prog)] = narastajaco
    poprzedni = prog

  if budynki is not None:
    puste = pd.Series(dtype=object)
    _dopisz_strefy(wiersz, BUDYNKI,
                   budynki["strefa"] if len(budynki) else puste)
    for przedrostek, rodzaj in ((BUDYNKI_MIESZKALNE, RODZAJ_MIESZKALNY),
                                (BUDYNKI_OSWIATA, RODZAJ_OSWIATA),
                                (BUDYNKI_ZDROWIE, RODZAJ_ZDROWIE)):
      wybrane = (budynki[budynki["RODZAJ"] == rodzaj]
                 if len(budynki) else budynki)
      _dopisz_strefy(wiersz, przedrostek,
                     wybrane["strefa"] if len(wybrane) else puste)

  if teren:
    wiersz.update(teren)
  return wiersz


def _tekst(wartosc):
  """Puste pole (NaN) na plaszczyzne — NaN jest prawdziwy logicznie,
  wiec zwykle `wartosc or "—"` go nie lapie."""
  return "—" if pd.isna(wartosc) or wartosc == "" else str(wartosc)


def _klucz_numeru(numer):
  """Naturalne sortowanie numerow: 55, 69, 116, 116B, 119a — nie 116, 119, 55."""
  tekst = "" if pd.isna(numer) else str(numer)
  czesci = re.split(r"(\d+)", tekst)
  # Krotka, nie lista — sort_values po wielu kolumnach wymaga wartosci haszowalnych.
  return tuple((int(c), "") if c.isdigit() else (0, c.lower()) for c in czesci if c)


def zapisz_liste_rozbiorek():
  """Czytelna lista adresow do rozbiorki, pogrupowana po miejscowosciach.

  Sklada sie z plikow wariant-*-rozbiorka.csv lezacych na dysku, nie z danych
  w pamieci — dzieki temu jest kompletna takze wtedy, gdy przeliczany byl
  tylko jeden wariant."""
  stan = stan_danych()
  L = ["# Adresy w śladzie planowanej drogi S7", ""]
  L.append("> **To wyliczenie, nie oficjalna lista wywłaszczeń.** Zestawienie powstało")
  L.append("> z materiałów konsultacji społecznych przez rekonstrukcję śladu drogi")
  L.append("> z linii krawędzi jezdni i skarp — obrys zajęcia terenu nie został")
  L.append("> opublikowany, więc ślad jest odtworzony, a nie przepisany. To nie jest")
  L.append("> decyzja administracyjna ani zapowiedź rozbiórki konkretnego budynku.")
  L.append(">")
  L.append("> Ograniczenia, o których trzeba wiedzieć:")
  L.append(">")
  L.append("> - punkt adresowy PRG to współrzędna, a nie obrys budynku — dom może stać")
  L.append(">   kilka metrów od punktu, więc pojedyncze trafienia mogą być mylne,")
  L.append("> - kategoria „nad tunelem” zakłada budowę metodą odkrywkową, czego materiały")
  L.append(">   nie rozstrzygają; nad tunelem drążonym budynki zostają,")
  L.append("> - dane adresowe: PRG (GUGiK){}.".format(
      ", stan na {}".format(stan.strftime("%d.%m.%Y")) if stan else ""))
  L.append(">")
  L.append("> Metoda, kalibracja i kontrole: README.md i warstwy.md w repozytorium")
  L.append("> <https://github.com/lechup/stop-s7>")
  L.append("")
  L.append("Poniżej punkty adresowe leżące w śladzie drogi lub w pasie wykopu nad")
  L.append("tunelem, pogrupowane po miejscowościach.")
  L.append("")
  for wariant in consts.VARIANTS:
    plik = "{}/wariant-{}-rozbiorka.csv".format(KATALOG_WYNIKOW, wariant)
    if not os.path.exists(plik):
      continue
    adresy = pd.read_csv(plik)
    L.append("## Wariant {}".format(wariant))
    L.append("")
    if adresy.empty:
      L.append("_Brak adresów._\n")
      continue
    L.append("Razem: **{}** adresów ({} w śladzie, {} nad tunelem).".format(
        len(adresy),
        int((adresy["strefa"] == W_SLADZIE).sum()),
        int((adresy["strefa"] == NAD_TUNELEM).sum())))
    L.append("")
    adresy = adresy.assign(_klucz=adresy["NUMER_PORZ"].map(_klucz_numeru))
    for msc, grupa in adresy.groupby("NAZWA_MSC", sort=True, dropna=False):
      grupa = grupa.sort_values(["NAZWA_ULC", "_klucz"], na_position="first")
      L.append("### {} ({})".format(_tekst(msc), len(grupa)))
      L.append("")
      L.append("| ulica | nr | kod | kategoria |")
      L.append("|---|---|---|---|")
      for _, r in grupa.iterrows():
        L.append("| {} | {} | {} | {} |".format(
            _tekst(r.get("NAZWA_ULC")), _tekst(r.get("NUMER_PORZ")),
            _tekst(r.get("KOD_POCZT")), r["strefa"]))
      L.append("")
  with open("{}/rozbiorka.md".format(KATALOG_WYNIKOW), "w") as f:
    f.write("\n".join(L) + "\n")


def zapisz_liste_dzialek():
  """Lista dzialek do zajecia, pogrupowana po obrebach.

  Wlasciciel gruntu bez zabudowy nie pojawia sie ani w rozbiorka.md, ani w zadnej
  statystyce budynkow czy adresow — a jego dzialka bywa zajeta tak samo. To
  jedyny dokument, w ktorym moze sie odnalezc."""
  L = ["# Działki do zajęcia pod planowaną drogę S7", ""]
  L.append("> **To wyliczenie, nie oficjalna lista wywłaszczeń.** Zestawienie powstało")
  L.append("> z materiałów konsultacji społecznych przez rekonstrukcję śladu drogi —")
  L.append("> obrys zajęcia terenu nie został opublikowany. To nie jest decyzja")
  L.append("> administracyjna ani zapowiedź wywłaszczenia konkretnej działki.")
  L.append(">")
  L.append("> Udział zajęcia liczony jest z powierzchni ewidencyjnej działki. Granice")
  L.append("> działek pochodzą z materiałów STEŚ, a nie wprost z ewidencji, więc przy")
  L.append("> małych udziałach różnica rzędu ułamka procenta jest w granicach błędu.")
  L.append(">")
  L.append("> Metoda i kontrole: README.md w repozytorium")
  L.append("> <https://github.com/lechup/stop-s7>")
  L.append("")

  cokolwiek = False
  for wariant in consts.VARIANTS:
    plik = "{}/wariant-{}-dzialki.csv".format(KATALOG_WYNIKOW, wariant)
    if not os.path.exists(plik):
      continue
    cokolwiek = True
    dzialki = pd.read_csv(plik)
    L.append("## Wariant {}".format(wariant))
    L.append("")
    if dzialki.empty:
      L.append("_Brak działek._\n")
      continue
    powyzej = [int((dzialki["udzial_proc"] > prog).sum()) for prog in PROGI_ZAJECIA]
    L.append("Razem: **{}** działek ({} zabudowanych). Zajętych w ponad {}%: {}, "
             "w ponad {}%: {}.".format(
                 len(dzialki), int(dzialki["zabudowana"].sum()),
                 PROGI_ZAJECIA[0], powyzej[0], PROGI_ZAJECIA[1], powyzej[1]))
    L.append("")
    # Najdotkliwiej zajete na gorze — to one decyduja o losie wlasciciela.
    for obreb, grupa in dzialki.groupby("obreb", sort=True, dropna=False):
      grupa = grupa.sort_values("udzial_proc", ascending=False)
      L.append("### {} ({})".format(_tekst(obreb), len(grupa)))
      L.append("")
      L.append("| nr działki | zajęte | powierzchnia | zabudowa | identyfikator |")
      L.append("|---|---|---|---|---|")
      for _, r in grupa.iterrows():
        udzial = r["udzial_proc"]
        L.append("| {} | {} | {} m² | {} | `{}` |".format(
            _tekst(r.get("nr_dzialki")),
            "<1%" if udzial < 1 else "{:.0f}%".format(udzial),
            "{:,.0f}".format(float(r.get("pow_m2") or 0)).replace(",", " "),
            "tak" if r.get("zabudowana") else "—",
            _tekst(r.get("teryt"))))
      L.append("")

  if not cokolwiek:
    return
  with open("{}/dzialki.md".format(KATALOG_WYNIKOW), "w") as f:
    f.write("\n".join(L) + "\n")


def generate(warianty=None, zapisz_slad=True, postep=print):
  warianty = warianty or consts.VARIANTS
  os.makedirs(KATALOG_WYNIKOW, exist_ok=True)

  podsumowania = []
  for wariant in warianty:
    postep("Wariant {}:".format(wariant))
    adresy, warstwy = policz(wariant, postep)
    if adresy is None:
      postep("  pomijam — brak warstw opisujacych droge")
      continue

    budynki = trafione_budynki(warstwy)
    podstawa = "{}/wariant-{}".format(KATALOG_WYNIKOW, wariant)
    adresy.drop(columns="geometry").to_csv(podstawa + "-adresy.csv", index=False)

    # Lista do rozbiorki: slad powierzchniowy + pas odkrywki nad tunelem.
    rozbiorka = adresy[adresy["strefa"].isin([W_SLADZIE, NAD_TUNELEM])]
    rozbiorka = rozbiorka.assign(
        _klucz=rozbiorka["NUMER_PORZ"].map(_klucz_numeru)).sort_values(
        ["NAZWA_MSC", "NAZWA_ULC", "_klucz"], na_position="first").drop(
        columns="_klucz")
    rozbiorka.drop(columns="geometry").to_csv(podstawa + "-rozbiorka.csv", index=False)

    zajete = zajete_dzialki(wariant, warstwy["korytarz"])
    if zajete is not None and len(zajete):
      zajete.drop(columns="geometry").to_csv(
          podstawa + "-dzialki.csv", index=False)

    if zapisz_slad:
      rodzaje, geom = [], []
      for nazwa in ("powierzchnia", "tunel"):
        if warstwy.get(nazwa) is not None and not shapely.is_empty(warstwy[nazwa]):
          rodzaje.append(nazwa)
          geom.append(warstwy[nazwa])

      sciezka_gpkg = podstawa + "-slad.gpkg"
      # Nadpisujemy od zera, zeby po przeliczeniu bez budynkow nie zostala
      # w pliku nieaktualna warstwa z poprzedniego uruchomienia.
      if os.path.exists(sciezka_gpkg):
        os.remove(sciezka_gpkg)

      gpd.GeoDataFrame({"rodzaj": rodzaje}, geometry=geom,
                       crs=consts.CRS_METRYCZNY).to_file(
          sciezka_gpkg, driver="GPKG", layer=WARSTWA_KORYTARZ)
      pas = warstwy.get("lacznice")
      if pas is not None and not shapely.is_empty(pas):
        gpd.GeoDataFrame({"rodzaj": ["lacznice"]}, geometry=[pas],
                         crs=consts.CRS_METRYCZNY).to_file(
            sciezka_gpkg, driver="GPKG", layer=WARSTWA_LACZNIC, mode="a")
      if budynki is not None and len(budynki):
        budynki.to_file(sciezka_gpkg, driver="GPKG",
                        layer=WARSTWA_BUDYNKI, mode="a")
      if len(adresy):
        adresy.to_file(sciezka_gpkg, driver="GPKG",
                       layer=WARSTWA_ADRESY, mode="a")

    teren = miary_terenu(wariant, warstwy["korytarz"])
    teren.update(miary_lacznic(wariant, warstwy["korytarz"],
                               warstwy.get("lacznice")))
    wiersz = podsumuj(wariant, adresy, budynki, teren)
    podsumowania.append(wiersz)
    postep("  do rozbiorki {} ({} w sladzie + {} nad tunelem), ≤200 m {}".format(
        wiersz[DO_ROZBIORKI], wiersz[W_SLADZIE], wiersz[NAD_TUNELEM],
        wiersz["≤{} m".format(consts.STREFY[-1])],))
    if budynki is not None:
      postep("  budynkow w korytarzu {} (mieszkalnych {}), ≤200 m {}".format(
          wiersz[BUDYNKI], wiersz[BUDYNKI_MIESZKALNE],
          wiersz["{} ≤{} m".format(BUDYNKI, consts.STREFY[-1])]))

  if not podsumowania:
    return None
  tabela = pd.DataFrame(podsumowania)
  # Kolejnosc kolumn ustala swiezo policzony wiersz. Stare podsumowanie moze
  # pochodzic sprzed dodania kolumn budynkowych i doklejaloby je na koncu.
  kolejnosc = list(tabela.columns)

  # Przy liczeniu podzbioru wariantow dopisujemy sie do istniejacego
  # podsumowania, zamiast je zastapic — inaczej "--wariant B" kasowalby
  # z tabeli wyniki pozostalych wariantow.
  sciezka = "{}/podsumowanie.csv".format(KATALOG_WYNIKOW)
  if os.path.exists(sciezka) and len(warianty) < len(consts.VARIANTS):
    stara = pd.read_csv(sciezka)
    stara = stara[~stara["wariant"].isin(tabela["wariant"])]
    tabela = pd.concat([stara, tabela], ignore_index=True)
  tabela = tabela.reindex(
      columns=kolejnosc + [k for k in tabela.columns if k not in kolejnosc])
  # Int64 (z wielka litera) dopuszcza braki, wiec wariant policzony bez
  # budynkow zostaje pusty zamiast zamieniac cala kolumne na 225.0.
  for kolumna in tabela.columns:
    if (kolumna.startswith(BUDYNKI) or kolumna.startswith("działki")):
      tabela[kolumna] = tabela[kolumna].astype("Int64")
  tabela = tabela.sort_values("wariant").reset_index(drop=True)
  tabela.to_csv(sciezka, index=False)
  zapisz_liste_rozbiorek()
  zapisz_liste_dzialek()
  # Pelna tabela ma ponad 50 kolumn — w terminalu pokazujemy przekroj,
  # komplet i tak idzie do podsumowanie.csv.
  skrot = ["wariant", W_SLADZIE, NAD_TUNELEM, DO_ROZBIORKI,
           "≤{} m".format(consts.STREFY[-1]), BUDYNKI, BUDYNKI_MIESZKALNE,
           BUDYNKI_OSWIATA, BUDYNKI_ZDROWIE, "działki", "zajęte [ha]"]
  skrot = [k for k in skrot if k in tabela.columns]
  postep("\n" + tabela[skrot].to_string(index=False))
  postep("\nZapisano {0}/podsumowanie.csv, {0}/rozbiorka.md i {0}/dzialki.md"
         .format(KATALOG_WYNIKOW))
  return tabela


def informacje_o_danych():
  """Co skrypt faktycznie czyta — do sprawdzenia po odswiezeniu danych."""
  sciezka = znajdz_plik_adresow()
  info = pyogrio.read_info(sciezka)
  stan = stan_danych()
  print("Punkty adresowe:")
  print("  plik      : {}".format(sciezka))
  print("  rekordow  : {}".format(info.get("features")))
  print("  uklad     : {}".format((info.get("crs") or "?")[:60]))
  print("  pola      : {}".format(", ".join(info.get("fields", []))))
  print("  stan danych: {}".format(stan.strftime("%d.%m.%Y") if stan else "nieustalony"))
  print()
  print("Warianty:")
  for wariant in consts.VARIANTS:
    sciezka_gml = geometria.sciezka(wariant)
    if not os.path.exists(sciezka_gml):
      print("  {}: BRAK PLIKU {}".format(wariant, sciezka_gml))
      continue
    nazwy = geometria.nazwy_warstw(wariant)
    braki = [r for r in consts.WARSTWY_SLADU + ["os"] if r not in nazwy]
    print("  {}: warstw {:<3} {}".format(
        wariant, len(nazwy),
        "komplet" if not braki else "brak: " + ", ".join(braki)))


def debug():
  """Inwentarz warstw w plikach GML — nazwy, typy, liczby obiektow."""
  for wariant in consts.VARIANTS:
    sciezka = geometria.sciezka(wariant)
    print("Wariant {} ({}):".format(wariant, sciezka))
    nazwy = geometria.nazwy_warstw(wariant)
    for nazwa in nazwy:
      info = pyogrio.read_info(sciezka, layer=nazwa)
      print("  {:<24} {:<16} n={}".format(
          nazwa, str(info.get("geometry_type")), info.get("features")))
    braki = [r for r in consts.WARSTWY_SLADU + ["os"] if r not in nazwy]
    print("  BRAKI: {}\n".format(", ".join(braki) if braki else "brak"))

def _rozbierz_zapytanie(zapytanie):
  """Dzieli "Osterwy 41P" na (nazwa, numer).

  Numerem jest ostatni czlon, jesli zaczyna sie od cyfry — adresy wiejskie
  bywaja bez ulicy ("Golkowice 116"), a numery miewaja litery ("41P", "37b")."""
  czesci = zapytanie.strip().split()
  if len(czesci) >= 2 and czesci[-1][:1].isdigit():
    return " ".join(czesci[:-1]), czesci[-1]
  return zapytanie.strip(), None


def znajdz_adres(zapytanie):
  """Wyszukuje punkty adresowe w danych PRG. Zwraca GeoDataFrame."""
  nazwa, numer = _rozbierz_zapytanie(zapytanie)
  bezpieczna = nazwa.replace("'", "''")

  if numer:
    warunek = "NUMER_PORZ = '{}'".format(numer.replace("'", "''"))
  else:
    warunek = ("NAZWA_ULC LIKE '%{0}%' OR NAZWA_MSC LIKE '%{0}%'".format(bezpieczna))

  gdf = gpd.read_file(znajdz_plik_adresow(), columns=KOLUMNY, where=warunek)
  if gdf.empty:
    return gdf
  if nazwa:
    wzorzec = nazwa.lower()
    pasuje = (gdf["NAZWA_ULC"].fillna("").str.lower().str.contains(wzorzec, regex=False)
              | gdf["NAZWA_MSC"].fillna("").str.lower().str.contains(wzorzec, regex=False))
    gdf = gdf[pasuje]
  return gdf.to_crs(consts.CRS_METRYCZNY)


def sprawdz_adres(zapytanie, postep=print):
  """Dla podanego adresu podaje odleglosc i strefe w kazdym wariancie."""
  znalezione = znajdz_adres(zapytanie)
  if znalezione.empty:
    postep("Nie znaleziono adresu pasujacego do '{}'.".format(zapytanie))
    return None

  brakujace = [w for w in consts.VARIANTS
               if not os.path.exists("{}/wariant-{}-slad.gpkg".format(KATALOG_WYNIKOW, w))]
  if brakujace:
    postep("Brak zapisanych sladow dla wariantow: {}.".format(", ".join(brakujace)))
    postep("Policz je najpierw: ./uruchom.sh")
    return None

  korytarze = {}
  for wariant in consts.VARIANTS:
    warstwy = gpd.read_file(
        "{}/wariant-{}-slad.gpkg".format(KATALOG_WYNIKOW, wariant),
        layer=WARSTWA_KORYTARZ)
    powierzchnia = warstwy[warstwy["rodzaj"] == "powierzchnia"]
    korytarze[wariant] = (
        shapely.union_all(warstwy.geometry.values),
        shapely.union_all(powierzchnia.geometry.values) if not powierzchnia.empty else None,
    )

  # Przy wielu trafieniach pelna tabelka na kazdy adres to sciana tekstu —
  # wtedy jedna linia na adres z najblizszym wariantem.
  zwiezle = len(znalezione) > SZCZEGOLOWO_DO
  if len(znalezione) > 1:
    postep("Pasuje {} adresow{}.\n".format(
        len(znalezione), " — skrocone do najblizszego wariantu" if zwiezle else ""))
  if zwiezle:
    postep("  {:<44} {:>10} {:>9}   {}".format(
        "adres", "najblizszy", "odleglosc", "strefa"))

  wyniki = []
  for _, adres in znalezione.iterrows():
    opis = "{} {}, {} {}".format(
        _tekst(adres["NAZWA_ULC"]), _tekst(adres["NUMER_PORZ"]),
        _tekst(adres["KOD_POCZT"]), _tekst(adres["NAZWA_MSC"]))
    if not zwiezle:
      postep(opis)
      postep("  {:<9} {:>14} {:>16}   {}".format(
          "wariant", "od korytarza", "od powierzchni", "strefa"))
    punkt = adres.geometry
    wiersze_adresu = []
    for wariant in consts.VARIANTS:
      korytarz, powierzchnia = korytarze[wariant]
      od_korytarza = shapely.distance(punkt, korytarz)
      od_powierzchni = (shapely.distance(punkt, powierzchnia)
                        if powierzchnia is not None else None)
      if od_korytarza > max(consts.STREFY):
        strefa = "poza {} m".format(max(consts.STREFY))
      elif od_powierzchni == 0:
        strefa = W_SLADZIE.upper()
      elif od_korytarza == 0:
        strefa = NAD_TUNELEM.upper()
      else:
        strefa = _strefa(od_korytarza)
      if not zwiezle:
        postep("  {:<9} {:>13.1f}m {:>15.1f}m   {}".format(
            wariant, od_korytarza,
            od_powierzchni if od_powierzchni is not None else float("nan"),
            strefa))
      wiersz = {"adres": opis, "wariant": wariant,
                "odleglosc_m": round(od_korytarza, 1), "strefa": strefa}
      wiersze_adresu.append(wiersz)
      wyniki.append(wiersz)

    if zwiezle:
      najblizszy = min(wiersze_adresu, key=lambda w: w["odleglosc_m"])
      postep("  {:<44} {:>10} {:>8.1f}m   {}".format(
          opis[:44], najblizszy["wariant"], najblizszy["odleglosc_m"],
          najblizszy["strefa"]))
    else:
      postep("")
  return pd.DataFrame(wyniki)
