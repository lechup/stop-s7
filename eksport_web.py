"""Eksportuje wyniki do postaci, ktora da sie wystawic na GitHub Pages.

Strona jest statyczna — zadnego backendu. Cale dane po zaokragleniu wspolrzednych
i kompresji waza ok. 300 kB, wiec nie ma po co siegac po kafelki wektorowe:
przegladarka bierze zwykly GeoJSON.

Powstaja dwie rzeczy:

  docs/dane/wariant-X.geojson  — korytarz, budynki i adresy jednego wariantu,
                                 rozroznione polem "warstwa"
  docs/dane/adresy-index.json  — indeks do wyszukiwarki: dla kazdego adresu
                                 odleglosc i strefa we WSZYSTKICH wariantach

Indeks jest osobny, bo warstwa "adresy" kazdego wariantu obejmuje tylko jego
wlasne otoczenie — zeby odpowiedziec "jak to wyglada u mnie we wszystkich
wariantach", trzeba policzyc kazdy adres wzgledem kazdego korytarza.

Uruchomienie:
    .venv/bin/python eksport_web.py
"""

import json
import os

import geopandas as gpd
import shapely

import consts
import functions

KATALOG = "docs/dane"
# Promien indeksu wyszukiwarki. Wiekszy niz raportowe 200 m, zeby ktos mieszkajacy
# tuz za granica strefy dostal konkretna liczbe zamiast "nie znaleziono".
PROMIEN_INDEKSU = 500
# Zaokraglenie wspolrzednych: 6 miejsc po przecinku to ok. 0,1 m — ponizej
# dokladnosci samych danych, a tnie rozmiar plikow o jedna trzecia.
MIEJSC = 6

# Kody stref w indeksie — krotkie, bo powtarzaja sie dziesiatki tysiecy razy.
POZA = 0
KODY_STREF = {
    functions.W_SLADZIE: 1,
    functions.NAD_TUNELEM: 2,
}


def zaokraglij(wartosc):
  if isinstance(wartosc, float):
    return round(wartosc, MIEJSC)
  if isinstance(wartosc, list):
    return [zaokraglij(v) for v in wartosc]
  return wartosc


def zapisz_json(sciezka, dane):
  # allow_nan=False, bo NaN i Infinity to literaly, ktorych JSON.parse
  # w przegladarce NIE przyjmuje — Python czyta je bez mrugniecia, wiec bez
  # tego bledny plik przeszedlby testy i wysypal sie dopiero u uzytkownika.
  with open(sciezka, "w", encoding="utf-8") as plik:
    json.dump(dane, plik, separators=(",", ":"), ensure_ascii=False,
              allow_nan=False)
  return os.path.getsize(sciezka)


def tekst(wartosc):
  """Pusta wartosc na pusty napis.

  Uwaga: brak w danych to NaN, a NaN jest logicznie PRAWDZIWY — zwykle
  `wartosc or ""` przepuscilby go dalej do pliku."""
  if wartosc is None or (isinstance(wartosc, float) and wartosc != wartosc):
    return ""
  return str(wartosc)


def warstwy_wariantu(wariant):
  """Trzy warstwy jednego wariantu w jednym GeoJSON-ie, z polem 'warstwa'."""
  sciezka = "raporty/wariant-{}-slad.gpkg".format(wariant)
  obiekty = []
  for warstwa in ("korytarz", "budynki", "adresy"):
    try:
      gdf = gpd.read_file(sciezka, layer=warstwa)
    except Exception:
      continue
    if gdf.empty:
      continue
    dane = json.loads(gdf.to_crs(4326).to_json(drop_id=True))
    for obiekt in dane["features"]:
      obiekt["geometry"]["coordinates"] = zaokraglij(
          obiekt["geometry"]["coordinates"])
      wlasciwosci = {k: v for k, v in obiekt["properties"].items()
                     if v is not None and v != ""}
      wlasciwosci["warstwa"] = warstwa
      obiekt["properties"] = wlasciwosci
    obiekty.extend(dane["features"])
  return {"type": "FeatureCollection", "features": obiekty}


def strefa_kod(od_korytarza, od_powierzchni):
  """Ta sama logika, co w functions.sprawdz_adres, sprowadzona do liczby."""
  if od_korytarza > max(consts.STREFY):
    return POZA
  if od_powierzchni is not None and od_powierzchni == 0:
    return KODY_STREF[functions.W_SLADZIE]
  if od_korytarza == 0:
    return KODY_STREF[functions.NAD_TUNELEM]
  nazwa = functions._strefa(od_korytarza)
  return 3 + consts.STREFY.index(int(nazwa.split("-")[1].split()[0]))


def indeks_adresow(korytarze, powierzchnie):
  """Adresy w promieniu PROMIEN_INDEKSU od ktoregokolwiek wariantu."""
  unia = shapely.union_all(list(korytarze.values()))
  obszar = shapely.buffer(unia, PROMIEN_INDEKSU)
  adresy = functions.wczytaj_adresy(obszar)
  trafienia = sorted(set(adresy.sindex.query(obszar, predicate="contains")))
  adresy = adresy.iloc[trafienia]
  wgs = adresy.to_crs(4326)

  wiersze = []
  for (_, rekord), punkt_wgs in zip(adresy.iterrows(), wgs.geometry):
    punkt = rekord.geometry
    pomiary = []
    for wariant in consts.VARIANTS:
      od_korytarza = shapely.distance(punkt, korytarze[wariant])
      powierzchnia = powierzchnie.get(wariant)
      od_powierzchni = (shapely.distance(punkt, powierzchnia)
                        if powierzchnia is not None else None)
      pomiary.append([round(od_korytarza),
                      strefa_kod(od_korytarza, od_powierzchni)])
    wiersze.append([
        tekst(rekord.get("NAZWA_ULC")),
        tekst(rekord.get("NUMER_PORZ")),
        tekst(rekord.get("NAZWA_MSC")),
        tekst(rekord.get("KOD_POCZT")),
        round(punkt_wgs.x, MIEJSC),
        round(punkt_wgs.y, MIEJSC),
        pomiary,
    ])
  return wiersze


if __name__ == "__main__":
  os.makedirs(KATALOG, exist_ok=True)

  korytarze, powierzchnie, szacunki = {}, {}, {}
  import pandas as pd
  podsumowanie = pd.read_csv("{}/podsumowanie.csv".format(
      functions.KATALOG_WYNIKOW)).fillna({"szacunek": ""})
  szacunki = dict(zip(podsumowanie["wariant"], podsumowanie["szacunek"] == "tak"))

  razem = 0
  for wariant in consts.VARIANTS:
    sciezka = "raporty/wariant-{}-slad.gpkg".format(wariant)
    if not os.path.exists(sciezka):
      print("  pomijam wariant {} — brak {}".format(wariant, sciezka))
      continue
    warstwy = gpd.read_file(sciezka, layer="korytarz")
    korytarze[wariant] = shapely.union_all(warstwy.geometry.values)
    powierzchnia = warstwy[warstwy["rodzaj"] == "powierzchnia"]
    powierzchnie[wariant] = (shapely.union_all(powierzchnia.geometry.values)
                             if not powierzchnia.empty else None)

    rozmiar = zapisz_json("{}/wariant-{}.geojson".format(KATALOG, wariant),
                          warstwy_wariantu(wariant))
    razem += rozmiar
    print("  wariant {}: {:.0f} kB".format(wariant, rozmiar / 1024))

  print("\nIndeks wyszukiwarki (promien {} m):".format(PROMIEN_INDEKSU))
  wiersze = indeks_adresow(korytarze, powierzchnie)
  rozmiar = zapisz_json("{}/adresy-index.json".format(KATALOG), {
      "warianty": consts.VARIANTS,
      "szacunek": [bool(szacunki.get(w)) for w in consts.VARIANTS],
      "progi": consts.STREFY,
      "promien": PROMIEN_INDEKSU,
      "adresy": wiersze,
  })
  razem += rozmiar
  print("  {} adresow, {:.0f} kB".format(len(wiersze), rozmiar / 1024))
  print("\nRazem {:.1f} MB w {}/".format(razem / 1048576, KATALOG))
