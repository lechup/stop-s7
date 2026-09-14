"""Odswieza punkty adresowe PRG: pobiera paczke, wycina wojewodztwo, konwertuje do SHP.

GUGiK nie publikuje juz paczek wojewodzkich w SHP pod stalym adresem — nazwy
plikow w paczce zbiorczej zawieraja znacznik czasu generowania
("12_malopolskie_11.09.2026_11.35.23.gml"), wiec nie da sie ich adresowac
bezposrednio. Zostaje paczka ogolnopolska (ok. 755 MB) w formacie GML.

Konwertujemy ja z powrotem do SHP o strukturze zgodnej z dotychczasowa, zeby
reszta kodu nie wymagala zmian — functions.znajdz_plik_adresow rozpoznaje plik
po kolumnach, nie po nazwie.

Roznica miedzy formatami jest istotna: w SHP nazwa miejscowosci i ulicy stoi
wprost przy punkcie adresowym, a w GML sa podlinkowane przez xlink:href do
osobnych obiektow AD_Miejscowosc i AD_UlicaPlac. Dlatego czytamy plik dwa razy:
najpierw slowniki, potem punkty.

GML nie zawiera nazwy gminy, tylko jej kod TERYT — nazwy bierzemy z poprzedniej
wersji pliku SHP (kody w GML maja 7 cyfr, w SHP 6: ostatnia to rodzaj gminy).

Uruchomienie:
    .venv/bin/python pobierz_prg.py             # wojewodztwo malopolskie
    .venv/bin/python pobierz_prg.py --kod 14    # inne wojewodztwo
"""

import argparse
import glob
import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import geopandas as gpd
import pandas as pd
import pyogrio

import consts

ZRODLO = "https://opendata.geoportal.gov.pl/prg/adresy/PRG-punkty_adresowe.zip"
KATALOG = "wojewodztwa-adresy"
ROBOCZY = "_pobrane"   # poza KATALOG: ten katalog trafia do archiwum

PRGAD = "{https://geoportal.gov.pl/schemas/prgad/1.0}"
GML = "{http://www.opengis.net/gml/3.2}"
XLINK = "{http://www.w3.org/1999/xlink}"

# Kolejnosc kolumn jak w dotychczasowym pliku SHP.
KOLUMNY = ["ID_IIP", "NUMER_PORZ", "KOD_POCZT", "DATA_NAD", "NAZWA_ULC",
           "ID_ULIC", "NAZWA_GMI", "TERYT_GMI", "NAZWA_MSC", "ID_SIMC"]


def tekst(element, nazwa):
  znaleziony = element.find(PRGAD + nazwa)
  return znaleziony.text if znaleziony is not None and znaleziony.text else None


def odnosnik(element, nazwa):
  znaleziony = element.find(PRGAD + nazwa)
  if znaleziony is None:
    return None
  cel = znaleziony.get(XLINK + "href")
  return cel.lstrip("#") if cel else None


def pobierz_paczke(sciezka):
  if os.path.exists(sciezka) and os.path.getsize(sciezka) > 0:
    print("  paczka juz pobrana ({:.0f} MB)".format(os.path.getsize(sciezka) / 1048576))
    return
  print("  pobieram {} ...".format(ZRODLO))
  os.makedirs(os.path.dirname(sciezka), exist_ok=True)
  with urllib.request.urlopen(ZRODLO, timeout=3000) as odpowiedz, \
       open(sciezka, "wb") as plik:
    pobrane = 0
    while True:
      kawalek = odpowiedz.read(4 * 1024 * 1024)
      if not kawalek:
        break
      plik.write(kawalek)
      pobrane += len(kawalek)
      print("\r    {:.0f} MB".format(pobrane / 1048576), end="", flush=True)
  print()


def wytnij_wojewodztwo(paczka, kod):
  """Wyciaga z paczki plik GML danego wojewodztwa (wpisy: '12_malopolskie_<data>.gml')."""
  with zipfile.ZipFile(paczka) as archiwum:
    pasujace = [w for w in archiwum.infolist()
                if os.path.basename(w.filename).startswith(kod + "_")]
    if not pasujace:
      dostepne = ", ".join(sorted(
          os.path.basename(w.filename)[:2] for w in archiwum.infolist()))
      raise SystemExit("Brak wojewodztwa '{}' w paczce. Dostepne: {}".format(
          kod, dostepne))
    wpis = pasujace[0]
    cel = os.path.join(ROBOCZY, os.path.basename(wpis.filename))
    if os.path.exists(cel) and os.path.getsize(cel) == wpis.file_size:
      print("  {} juz rozpakowany".format(os.path.basename(cel)))
      return cel
    print("  rozpakowuje {} ({:.0f} MB)...".format(
        os.path.basename(wpis.filename), wpis.file_size / 1048576))
    with archiwum.open(wpis) as zrodlo, open(cel, "wb") as plik:
      while True:
        kawalek = zrodlo.read(8 * 1024 * 1024)
        if not kawalek:
          break
        plik.write(kawalek)
    return cel


def slowniki(sciezka_gml):
  """Pierwszy przebieg: miejscowosci i ulice, po ktorych punkty sie odwoluja."""
  miejscowosci, ulice = {}, {}
  for _zdarzenie, element in ET.iterparse(sciezka_gml, events=("end",)):
    if element.tag == PRGAD + "AD_Miejscowosc":
      miejscowosci[element.get(GML + "id")] = (
          tekst(element, "nazwa"),
          tekst(element, "TERYTGminy"),
          tekst(element, "identyfikatorSIMC"),
      )
      element.clear()
    elif element.tag == PRGAD + "AD_UlicaPlac":
      ulice[element.get(GML + "id")] = (
          tekst(element, "nazwaPelna"),
          tekst(element, "identyfikatorULIC"),
      )
      element.clear()
  print("  miejscowosci: {}, ulic: {}".format(len(miejscowosci), len(ulice)))
  return miejscowosci, ulice


def punkty(sciezka_gml, miejscowosci, ulice, nazwy_gmin):
  """Drugi przebieg: punkty adresowe z rozwiazanymi odnosnikami."""
  wiersze, iksy, igreki = [], [], []
  for _zdarzenie, element in ET.iterparse(sciezka_gml, events=("end",)):
    if element.tag != PRGAD + "AD_PunktAdresowy":
      continue

    punkt = element.find(PRGAD + "georeferencja/" + GML + "Point/" + GML + "pos")
    if punkt is None or not punkt.text:
      element.clear()
      continue
    # srsName="EPSG:2180" (nie urn), wiec kolejnosc to easting northing.
    wschod, polnoc = (float(v) for v in punkt.text.split()[:2])

    nazwa_msc, teryt7, simc = miejscowosci.get(odnosnik(element, "miejscowosc"),
                                               (None, None, None))
    nazwa_ulc, ulic = ulice.get(odnosnik(element, "ulica2"), (None, None))
    teryt6 = teryt7[:6] if teryt7 else None

    lokalny = element.find(
        PRGAD + "idIIP/" + PRGAD + "AD_IdentyfikatorIIP/" + PRGAD + "lokalnyId")

    wiersze.append((
        lokalny.text if lokalny is not None else None,
        tekst(element, "numerPorzadkowy"),
        tekst(element, "kodPocztowy"),
        tekst(element, "dataNadania"),
        nazwa_ulc,
        ulic,
        nazwy_gmin.get(teryt6),
        teryt6,
        nazwa_msc,
        simc,
    ))
    iksy.append(wschod)
    igreki.append(polnoc)
    element.clear()

  tabela = pd.DataFrame(wiersze, columns=KOLUMNY)
  return gpd.GeoDataFrame(
      tabela, geometry=gpd.points_from_xy(iksy, igreki),
      crs=consts.CRS_METRYCZNY)


def nazwy_gmin_z_poprzedniego():
  """TERYT gminy -> nazwa, z poprzedniej wersji pliku (GML nie niesie nazw gmin)."""
  kandydaci = sorted(glob.glob(
      os.path.join(KATALOG, "**", "*PunktyAdresowe*.shp"), recursive=True))
  for sciezka in kandydaci:
    try:
      pola = set(pyogrio.read_info(sciezka)["fields"])
      if not {"TERYT_GMI", "NAZWA_GMI"} <= pola:
        continue
      dane = pyogrio.read_dataframe(
          sciezka, columns=["TERYT_GMI", "NAZWA_GMI"], read_geometry=False)
    except Exception:
      continue
    dane = dane.dropna().drop_duplicates("TERYT_GMI")
    slownik = dict(zip(dane["TERYT_GMI"].astype(str), dane["NAZWA_GMI"]))
    if slownik:
      print("  nazwy gmin z {} ({} gmin)".format(sciezka, len(slownik)))
      return slownik
  print("  UWAGA: nie znalazlem poprzedniego pliku — NAZWA_GMI zostanie pusta")
  return {}


parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--kod", default="12",
                    help="Dwucyfrowy kod wojewodztwa (domyslnie 12 — malopolskie)")
parser.add_argument("--katalog", default="malopolska",
                    help="Podkatalog w {}/ na wynik".format(KATALOG))
parser.add_argument("--zostaw-paczke", action="store_true",
                    help="Nie kasuj pobranej paczki i rozpakowanego GML-a")

if __name__ == "__main__":
  args = parser.parse_args()
  os.makedirs(ROBOCZY, exist_ok=True)
  paczka = os.path.join(ROBOCZY, "PRG-punkty_adresowe.zip")

  print("Paczka PRG:")
  pobierz_paczke(paczka)
  sciezka_gml = wytnij_wojewodztwo(paczka, args.kod)

  print("\nSlowniki (pierwszy przebieg):")
  nazwy_gmin = nazwy_gmin_z_poprzedniego()
  miejscowosci, ulice = slowniki(sciezka_gml)

  print("\nPunkty adresowe (drugi przebieg):")
  adresy = punkty(sciezka_gml, miejscowosci, ulice, nazwy_gmin)
  print("  wczytano {} punktow".format(len(adresy)))

  katalog_celu = os.path.join(KATALOG, args.katalog)
  os.makedirs(katalog_celu, exist_ok=True)
  cel = os.path.join(katalog_celu, "PRG_PunktyAdresowe_{}.shp".format(args.kod))
  adresy.to_file(cel, driver="ESRI Shapefile", encoding="utf-8")
  print("\nZapisano {} ({} rekordow)".format(cel, len(adresy)))

  braki = {k: int(adresy[k].isna().sum()) for k in KOLUMNY}
  print("  puste pola: {}".format(
      ", ".join("{}={}".format(k, v) for k, v in braki.items() if v)))

  if not args.zostaw_paczke:
    for sciezka in (paczka, sciezka_gml):
      if os.path.exists(sciezka):
        os.remove(sciezka)
    if os.path.isdir(ROBOCZY) and not os.listdir(ROBOCZY):
      os.rmdir(ROBOCZY)
