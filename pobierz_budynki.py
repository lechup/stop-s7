"""Pobiera obrysy budynkow z EGIB (WFS GUGiK) dla korytarza wszystkich wariantow.

Punkt adresowy PRG to wspolrzedna, a nie obrys budynku — dom moze stac kilka
metrow od punktu. Obrysy z ewidencji gruntow i budynkow pozwalaja liczyc
trafienia po rzeczywistym ksztalcie budynku.

Zakres: wspolny korytarz wszystkich wariantow poszerzony o najdalsza strefe
(200 m), czyli dokladnie tyle, ile potrzeba do wypelnienia calej tabeli wynikow.
Odpytujemy prostokatem opisanym na tym obszarze (filtr WFS ma byc krotki
i prosty), a do wlasciwego ksztaltu przycinamy juz lokalnie.

UWAGA na kolejnosc osi: przy srsName "urn:ogc:def:crs:EPSG::2180" wspolrzedne
ida jako "northing easting" — odwrotnie niz podaje GeoPandas. Zamiana miejscami
NIE konczy sie bledem: serwer zwraca komplet budynkow, tylko z innego miejsca
w Polsce. Dlatego po pobraniu sprawdzamy, czy geometria wpada w korytarz.

Uruchomienie:
    .venv/bin/python pobierz_budynki.py           # pobierz i zloz
    .venv/bin/python pobierz_budynki.py --od-nowa # ignoruj cache stron
"""

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
import shapely

import consts

SERWIS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza"
WARSTWA = "ms:budynki"
CRS_URN = "urn:ogc:def:crs:EPSG::2180"

# Serwer zwraca maksymalnie 1000 obiektow na zadanie niezaleznie od "count".
NA_STRONE = 1000
PRZERWA = 1.0          # [s] miedzy zadaniami — nie dobijamy sie do uslugi
PROBY = 4
LIMIT_CZASU = 300      # [s]; pierwsze zadanie potrafi isc ponad 100 s

KATALOG = "budynki"
KATALOG_STRON = os.path.join(KATALOG, "strony")
WYNIK = os.path.join(KATALOG, "budynki.gpkg")
KATALOG_SLADOW = "raporty"


def korytarz():
  """Wspolny korytarz wszystkich wariantow, poszerzony o najdalsza strefe."""
  slady = []
  for wariant in consts.VARIANTS:
    sciezka = "{}/wariant-{}-slad.gpkg".format(KATALOG_SLADOW, wariant)
    if not os.path.exists(sciezka):
      continue
    warstwy = gpd.read_file(sciezka)
    slady.append(shapely.union_all(warstwy.geometry.values))
  if not slady:
    raise SystemExit(
        "Brak plikow {}/wariant-*-slad.gpkg — policz najpierw slady:\n"
        "  ./uruchom.sh".format(KATALOG_SLADOW))
  return shapely.buffer(shapely.union_all(slady), max(consts.STREFY))


def filtr_prostokata(granice):
  """Filtr WFS dla prostokata. Pary wspolrzednych ida jako 'northing easting'."""
  minx, miny, maxx, maxy = granice
  rogi = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
  pozycje = " ".join("{:.2f} {:.2f}".format(y, x) for x, y in rogi)
  return (
      "<fes:Filter><fes:Intersects>"
      "<fes:ValueReference>ms:msGeometry</fes:ValueReference>"
      '<gml:Polygon srsName="{}" gml:id="P1">'
      "<gml:exterior><gml:LinearRing><gml:posList>{}</gml:posList>"
      "</gml:LinearRing></gml:exterior>"
      "</gml:Polygon></fes:Intersects></fes:Filter>".format(CRS_URN, pozycje))


def adres(filtr, **dodatkowe):
  parametry = {
      "service": "wfs",
      "request": "GetFeature",
      "version": "2.0.0",
      "srsname": CRS_URN,
      "typenames": WARSTWA,
      "filter": filtr,
  }
  parametry.update(dodatkowe)
  return SERWIS + "?" + urllib.parse.urlencode(parametry)


def pobierz(url, opis):
  """Pobiera adres, ponawiajac przy bledzie sieci z rosnaca przerwa."""
  for proba in range(1, PROBY + 1):
    try:
      with urllib.request.urlopen(url, timeout=LIMIT_CZASU) as odpowiedz:
        return odpowiedz.read()
    except (urllib.error.URLError, OSError) as blad:
      if proba == PROBY:
        raise SystemExit("\n{}: nie udalo sie po {} probach ({})".format(
            opis, PROBY, blad))
      czekaj = 5 * proba
      print("\n  {} — {}; ponawiam za {} s (proba {}/{})".format(
          opis, str(blad)[:60], czekaj, proba + 1, PROBY))
      time.sleep(czekaj)


def ile_obiektow(filtr):
  tresc = pobierz(adres(filtr, resulttype="hits"), "zliczanie obiektow")
  dopasowanie = re.search(rb'numberMatched="(\d+)"', tresc)
  return int(dopasowanie.group(1)) if dopasowanie else None


def pobierz_strony(filtr, razem, od_nowa=False):
  """Pobiera kolejne strony wynikow. Gotowe strony pomija, wiec da sie wznowic."""
  os.makedirs(KATALOG_STRON, exist_ok=True)
  pliki = []
  indeks = 0
  numer = 0
  while True:
    numer += 1
    plik = os.path.join(KATALOG_STRON, "strona-{:06d}.gml".format(indeks))
    pliki.append(plik)

    if os.path.exists(plik) and os.path.getsize(plik) > 0 and not od_nowa:
      zwrocone = NA_STRONE
      print("  strona {:>3} (od {:>6}) — juz pobrana".format(numer, indeks))
    else:
      url = adres(filtr, count=str(NA_STRONE), startindex=str(indeks))
      start = time.time()
      tresc = pobierz(url, "strona od {}".format(indeks))
      dopasowanie = re.search(rb'numberReturned="(\d+)"', tresc)
      zwrocone = int(dopasowanie.group(1)) if dopasowanie else 0
      if zwrocone:
        with open(plik, "wb") as f:
          f.write(tresc)
      else:
        pliki.pop()
      print("  strona {:>3} (od {:>6}) — {:>4} obiektow, {:.1f} MB, {:.1f}s".format(
          numer, indeks, zwrocone, len(tresc) / 1048576, time.time() - start))
      time.sleep(PRZERWA)

    indeks += NA_STRONE
    if zwrocone < NA_STRONE:
      break
    if razem and indeks >= razem:
      break
  return pliki


def zloz(pliki, obszar):
  """Laczy strony, odsiewa powtorzenia i przycina do wlasciwego ksztaltu."""
  kawalki = []
  for plik in pliki:
    if not os.path.exists(plik):
      continue
    try:
      gdf = gpd.read_file(plik)
    except Exception as blad:
      print("  pomijam {} — {}".format(os.path.basename(plik), str(blad)[:60]))
      continue
    if not gdf.empty:
      kawalki.append(gdf)
  if not kawalki:
    raise SystemExit("Nie udalo sie odczytac zadnej strony.")

  budynki = gpd.GeoDataFrame(
      pd.concat(kawalki, ignore_index=True), crs=kawalki[0].crs)
  przed = len(budynki)

  # ID_BUDYNKU i gml_id bywaja doslownie "None", wiec kluczem jest geometria.
  budynki = budynki[budynki.geometry.notna() & ~budynki.geometry.is_empty]
  budynki = budynki.loc[~budynki.geometry.apply(lambda g: g.wkb).duplicated()]
  po_odsianiu = len(budynki)

  budynki = budynki.to_crs(consts.CRS_METRYCZNY)
  trafienia = budynki.sindex.query(obszar, predicate="intersects")
  budynki = budynki.iloc[sorted(trafienia)].reset_index(drop=True)

  print("\n  wczytano {} obiektow, po odsianiu powtorzen {}, w korytarzu {}".format(
      przed, po_odsianiu, len(budynki)))
  return budynki


def sprawdz_polozenie(budynki, obszar):
  """Kontrola kolejnosci osi — zla zamiana daje budynki gdzie indziej w Polsce."""
  if budynki.empty:
    raise SystemExit(
        "Zaden budynek nie trafil w korytarz. Najczestsza przyczyna to odwrocona\n"
        "kolejnosc osi w filtrze (ma byc 'northing easting').")
  wlasne = shapely.bounds(obszar)
  ich = budynki.total_bounds
  print("  korytarz : {:.0f} {:.0f} .. {:.0f} {:.0f}".format(*wlasne))
  print("  budynki  : {:.0f} {:.0f} .. {:.0f} {:.0f}".format(*ich))


parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--od-nowa", action="store_true",
                    help="Pobierz wszystkie strony na nowo, ignorujac cache")
parser.add_argument("--zostaw-strony", action="store_true",
                    help="Nie kasuj pobranych stron GML po zlozeniu wyniku")

if __name__ == "__main__":
  args = parser.parse_args()

  obszar = korytarz()
  granice = shapely.bounds(obszar)
  print("Korytarz wszystkich wariantow + {} m:".format(max(consts.STREFY)))
  print("  powierzchnia {:.1f} km2, prostokat odpytania {:.1f} km2".format(
      shapely.area(obszar) / 1e6,
      (granice[2] - granice[0]) * (granice[3] - granice[1]) / 1e6))

  filtr = filtr_prostokata(granice)
  razem = ile_obiektow(filtr)
  print("  obiektow w prostokacie: {}\n".format(razem if razem else "nieznana liczba"))

  pliki = pobierz_strony(filtr, razem, od_nowa=args.od_nowa)
  budynki = zloz(pliki, obszar)
  sprawdz_polozenie(budynki, obszar)

  os.makedirs(KATALOG, exist_ok=True)
  budynki.to_file(WYNIK, driver="GPKG", layer="budynki")
  print("\nZapisano {} ({} budynkow, {:.1f} MB)".format(
      WYNIK, len(budynki), os.path.getsize(WYNIK) / 1048576))

  if not args.zostaw_strony:
    for plik in pliki:
      if os.path.exists(plik):
        os.remove(plik)
    if os.path.isdir(KATALOG_STRON) and not os.listdir(KATALOG_STRON):
      os.rmdir(KATALOG_STRON)
