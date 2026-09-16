"""Pobiera warstwy wariantow S7 z serwisow konsultacyjnych STES.

Materialy konsultacyjne wystawione sa jako eksporty qgis2web — kazda warstwa to
plik JS z GeoJSON-em w srodku. Zrodlo jest wyrazie lepsze od plikow GML, ktorych
uzywalismy wczesniej:

  - ma warstwe skarp dla WSZYSTKICH wariantow, takze dla B, ktory w GML-u jej nie
    mial i przez to wymagal szacowania,
  - skarpy sa jedna spojna warstwa zamiast pokawalkowanych part_aa..part_ad,
  - dochodza warstwy, ktorych nie bylo wcale: krawedzie jezdni, dzialki
    ewidencyjne, osuwiska, tereny zalewowe, obszary chronione, kilometraz,
  - GeoJSON zamiast GML, wiec odpada konwersja i pliki .gfs.

Os trasy jest identyczna co do wspolrzednej z dotychczasowa (odleglosc
Hausdorffa 0,00 m), wiec to ten sam zestaw danych w lepszej formie, a nie
zmieniony przebieg.

UWAGA: numeracja warstw rozni sie miedzy wariantami (skarpy_24 w A-C, skarpy_21
w D i F, skarpy_22 w E), wiec nazwy odkrywamy z HTML-a strony, a nie zgadujemy.

Uruchomienie:
    .venv/bin/python pobierz_warianty.py
    .venv/bin/python pobierz_warianty.py --wariant A --wariant B
"""

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

import geopandas as gpd

import consts

ADRES = "https://wariant-w{}.s7-krakow-myslenice-stes.pl/"
KATALOG = "warianty"
ROBOCZY = "_pobrane/warianty"
PRZERWA = 0.5          # [s] miedzy pobraniami — nie dobijamy sie do serwisu
LIMIT_CZASU = 300
PROBY = 3

# Nazwa warstwy w serwisie (bez koncowego _NN) -> nazwa warstwy w naszym GPKG.
# Rola decyduje o tym, jak warstwa jest uzywana; nazwy trzymamy po polsku,
# bo tak samo nazywaja sie w raportach i na mapie.
ROLE = {
    "otrasyS7": "os",
    "otrasyBDI": "os_bdi",
    "otrasyS7wtunelu": "os_tunel",
    "otrasyBDIwtunelu": "os_tunel_bdi",
    "pobocze": "jezdnia",
    "krawdziejezdni": "krawedzie",
    "skarpy": "skarpy",
    "projektowanetunele": "tunele",
    "projektowaneestakadyimosty": "estakady",
    "proponowanalokalizacjaMOP": "mop",
    "proponowanyukaddrogowywzwdrogowych": "uklad_wezlow",
    "proponowanalokalizacjawzwdrogowych": "wezly",
    "nazwywzwdrogowych": "nazwy_wezlow",
    "schematizakresbudowylubprzebudowy": "zakres_budowy",
    "kilometraco1km": "kilometraz_1km",
    "kilometraco100m": "kilometraz_100m",
    "granicedziaekewidencyjnych": "dzialki",
    "graniceobrbwewidencyjnych": "obreby",
    "granicegmin": "gminy",
    "granicepowiatw": "powiaty",
    "obszaryosuwisk": "osuwiska",
    "obszaryzagrooneruchamimasowymi": "ruchy_masowe",
    "terenychronioneprzyrodniczo": "chronione",
    "pomnikiprzyrody": "pomniki_przyrody",
    "S52BielskoBiaaGogoczw": "s52",
}
# Warstwy powodziowe maja bardzo dluga, niestabilna nazwe — dopasowujemy wzorcem.
WZORZEC_POWODZI = re.compile(r"^zakresterenwzagroonychpowodzi")

# Warstwy kontekstowe sa BAJT W BAJT identyczne we wszystkich wariantach
# (sprawdzone sumami sha256 pobranych plikow). Trzymanie ich w szesciu kopiach
# kosztowaloby 255 MB nadmiaru, wiec ida do osobnego pliku kontekst.gpkg.
WSPOLNE = {
    "s52", "gminy", "obreby", "powiaty", "osuwiska", "ruchy_masowe",
    "pomniki_przyrody", "chronione", "powodz",
}
PLIK_KONTEKSTU = "kontekst.gpkg"


def rola_warstwy(nazwa_pliku):
  """Zamienia 'skarpy_24.js' na nazwe warstwy w GPKG albo None, gdy pomijamy."""
  podstawa = re.sub(r"_\d+$", "", nazwa_pliku.removesuffix(".js"))
  if WZORZEC_POWODZI.match(podstawa):
    return "powodz"
  return ROLE.get(podstawa)


def pobierz(adres, opis):
  for proba in range(1, PROBY + 1):
    try:
      with urllib.request.urlopen(adres, timeout=LIMIT_CZASU) as odpowiedz:
        return odpowiedz.read()
    except (urllib.error.URLError, OSError) as blad:
      if proba == PROBY:
        raise SystemExit("\n{}: nie udalo sie po {} probach ({})".format(
            opis, PROBY, blad))
      print("\n  {} — {}; ponawiam".format(opis, str(blad)[:60]))
      time.sleep(3 * proba)


def nazwy_warstw(wariant):
  """Odkrywa warstwy ze strony wariantu — numeracja rozni sie miedzy nimi."""
  html = pobierz(ADRES.format(wariant.lower()),
                 "strona wariantu {}".format(wariant)).decode("utf-8", "replace")
  return sorted(set(re.findall(r'src="layers/([^"]+\.js)"', html)))


def wczytaj_warstwe(tresc):
  """Wyluskuje GeoJSON z 'var json_nazwa = {...};'."""
  tekst = tresc.decode("utf-8", "replace")
  dopasowanie = re.search(r"=\s*(\{.*\})\s*;?\s*$", tekst, re.S)
  if not dopasowanie:
    return None
  return json.loads(dopasowanie.group(1))


def sciezka_cache(wariant, plik):
  return os.path.join(ROBOCZY, wariant, plik)


def pobierz_wariant(wariant, postep=print):
  """Pobiera wszystkie rozpoznane warstwy wariantu do cache'u. Zwraca {rola: sciezka}."""
  os.makedirs(os.path.join(ROBOCZY, wariant), exist_ok=True)
  zebrane = {}
  for plik in nazwy_warstw(wariant):
    rola = rola_warstwy(plik)
    if not rola:
      continue
    cel = sciezka_cache(wariant, plik)
    if os.path.exists(cel) and os.path.getsize(cel) > 0:
      postep("    {:<22} z cache".format(rola))
    else:
      tresc = pobierz(ADRES.format(wariant.lower()) + "layers/" + plik,
                      "{} / {}".format(wariant, plik))
      with open(cel, "wb") as f:
        f.write(tresc)
      postep("    {:<22} {:>8.1f} kB".format(rola, len(tresc) / 1024))
      time.sleep(PRZERWA)
    # Kilka plikow moze mapowac sie na te sama role (np. dwie osie tunelowe).
    zebrane.setdefault(rola, []).append(cel)
  return zebrane


def wczytaj_role(pliki):
  """Laczy pliki jednej roli w GeoDataFrame w ukladzie metrycznym."""
  kawalki = []
  for sciezka in pliki:
    with open(sciezka, "rb") as f:
      dane = wczytaj_warstwe(f.read())
    if not dane or not dane.get("features"):
      continue
    kawalki.append(gpd.GeoDataFrame.from_features(dane["features"], crs=4326))
  if not kawalki:
    return None
  import pandas as pd
  gdf = kawalki[0] if len(kawalki) == 1 else gpd.GeoDataFrame(
      pd.concat(kawalki, ignore_index=True), crs=4326)
  gdf = gdf.to_crs(consts.CRS_METRYCZNY)
  # qgis2web niesie atrybuty z DXF-a; zostawiamy tylko te, ktore cos znacza.
  zbedne = [k for k in ("PaperSpace", "SubClasses", "EntityHandle", "Linetype")
            if k in gdf.columns]
  return gdf.drop(columns=zbedne)


def zloz_kontekst(zebrane, postep=print):
  """Sklada warstwy wspolne dla wszystkich wariantow w jeden plik."""
  os.makedirs(KATALOG, exist_ok=True)
  cel = os.path.join(KATALOG, PLIK_KONTEKSTU)
  if os.path.exists(cel):
    return cel, 0
  zapisane = 0
  for rola in sorted(WSPOLNE):
    if rola not in zebrane:
      continue
    gdf = wczytaj_role(zebrane[rola])
    if gdf is None:
      continue
    gdf.to_file(cel, driver="GPKG", layer=rola, mode="a" if zapisane else "w")
    zapisane += 1
    postep("    {:<22} {:>7} obiektow".format(rola, len(gdf)))
  return cel, zapisane


def zloz_gpkg(wariant, zebrane, postep=print):
  """Sklada warstwy WLASNE wariantu w jeden GPKG w ukladzie metrycznym."""
  os.makedirs(KATALOG, exist_ok=True)
  cel = os.path.join(KATALOG, "wariant-{}.gpkg".format(wariant))
  if os.path.exists(cel):
    os.remove(cel)

  zapisane = 0
  for rola, pliki in sorted(zebrane.items()):
    if rola in WSPOLNE:
      continue
    gdf = wczytaj_role(pliki)
    if gdf is None:
      continue
    gdf.to_file(cel, driver="GPKG", layer=rola, mode="a" if zapisane else "w")
    zapisane += 1
    postep("    {:<22} {:>7} obiektow".format(rola, len(gdf)))
  return cel, zapisane


parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--wariant", action="append", choices=consts.VARIANTS,
                    help="Ogranicz do wybranych wariantow; domyslnie wszystkie")
parser.add_argument("--zostaw-cache", action="store_true",
                    help="Nie kasuj pobranych plikow JS po zlozeniu GPKG")

if __name__ == "__main__":
  args = parser.parse_args()
  warianty = args.wariant or consts.VARIANTS
  kontekst_zlozony = False
  for wariant in warianty:
    print("Wariant {}:".format(wariant))
    zebrane = pobierz_wariant(wariant)
    print("  skladam GPKG:")
    cel, ile = zloz_gpkg(wariant, zebrane)
    print("  -> {} ({} warstw, {:.1f} MB)".format(
        cel, ile, os.path.getsize(cel) / 1048576))

    if not kontekst_zlozony:
      sciezka = os.path.join(KATALOG, PLIK_KONTEKSTU)
      if not os.path.exists(sciezka):
        print("  skladam warstwy wspolne (raz dla wszystkich wariantow):")
        sciezka, ile_k = zloz_kontekst(zebrane)
        print("  -> {} ({} warstw, {:.1f} MB)".format(
            sciezka, ile_k, os.path.getsize(sciezka) / 1048576))
      kontekst_zlozony = True
    print()
