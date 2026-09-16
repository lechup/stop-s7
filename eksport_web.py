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
from consts import nazwa_rodzaju
import functions

KATALOG = "docs/dane"
# Promien indeksu wyszukiwarki. Wiekszy niz raportowe 200 m, zeby ktos mieszkajacy
# tuz za granica strefy dostal konkretna liczbe zamiast "nie znaleziono" —
# komunikatu nieodroznialnego od literowki.
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


# Warstwy kontekstowe na mapie. Dzialki pokazujemy tylko te, ktore przecinaja
# korytarz — czyli dokladnie te, ktore raport liczy jako zajete; dzialki, ktorej
# na mapie nie ma, droga nie tyka. Reszta to warstwy pogladowe, przycinane do
# PROMIEN_KONTEKSTU, zeby nie ciagnac na strone calego wojewodztwa.
PROMIEN_KONTEKSTU = 500
KONTEKST = {
    "osuwiska": "osuwiska",
    "ruchy_masowe": "ruchy masowe",
    "powodz": "tereny zalewowe",
    "chronione": "obszary chronione",
}

# Rodzaj obiektu siedzi w atrybucie "Layer" — to nazwa warstwy CAD-owej
# z projektu. Pozostale atrybuty sa bezuzyteczne: "EntityHand" to uchwyt
# obiektu w DXF-ie, a "Text" to nazwa wzoru kreskowania ("SOLID").
# Rozroznienie ma znaczenie merytoryczne: osuwisko czynne pod planowana droga
# to co innego niz nieczynne.
def warstwy_kontekstowe(korytarz, postep=print):
  """Warstwy terenowe przyciete do otoczenia korytarza."""
  import geopandas as gpd
  obszar = shapely.buffer(korytarz, PROMIEN_KONTEKSTU)
  obiekty = []
  for warstwa, opis in KONTEKST.items():
    try:
      gdf = gpd.read_file("warianty/kontekst.gpkg", layer=warstwa)
    except Exception:
      continue
    gdf = gdf.to_crs(consts.CRS_METRYCZNY)
    gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
    trafione = gdf.iloc[sorted(set(gdf.sindex.query(obszar, predicate="intersects")))]
    if trafione.empty:
      continue
    # Przycinamy geometrie, a nie tylko filtrujemy — inaczej pojedynczy wielki
    # obszar chroniony przyciagnalby na strone pol wojewodztwa.
    przyciete = trafione.copy()
    przyciete["geometry"] = shapely.intersection(trafione.geometry.values, obszar)
    przyciete = przyciete[~przyciete.geometry.is_empty]
    if przyciete.empty:
      continue
    # Rozbicie na pojedyncze czesci: kazdy rodzaj przychodzi jako jeden
    # MultiPolygon, a Leaflet umieszcza podpis w srodku calej geometrii —
    # etykieta ladowala wiec w pustym miejscu miedzy odleglymi plamami.
    przyciete = przyciete.explode(index_parts=False, ignore_index=True)
    przyciete = przyciete[przyciete.geometry.area > 100]
    if przyciete.empty:
      continue
    dane = json.loads(przyciete.to_crs(4326).to_json(drop_id=True))
    for obiekt, (_, rekord) in zip(dane["features"], przyciete.iterrows()):
      obiekt["geometry"]["coordinates"] = zaokraglij(obiekt["geometry"]["coordinates"])
      obiekt["properties"] = {
          "warstwa": warstwa,
          "opis": nazwa_rodzaju(rekord.get("Layer"), opis),
          # Pole w hektarach: na jego podstawie strona decyduje, ktore obiekty
          # dostana staly podpis. Wszystkich jest ponad tysiac, wiec podpisanie
          # kazdego zamienialoby mape w platanine.
          "ha": round(rekord.geometry.area / 10000, 1),
      }
    obiekty.extend(dane["features"])
    postep("    {:<18} {:>5} obiektow".format(warstwa, len(dane["features"])))
  return obiekty


def warstwa_dzialek(wariant, korytarz, postep=print):
  """Dzialki ewidencyjne przecinajace korytarz."""
  import geopandas as gpd
  try:
    gdf = gpd.read_file("warianty/wariant-{}.gpkg".format(wariant), layer="dzialki")
  except Exception:
    return []
  gdf = gdf.to_crs(consts.CRS_METRYCZNY)
  gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
  trafione = gdf.iloc[sorted(set(gdf.sindex.query(korytarz, predicate="intersects")))]
  if trafione.empty:
    return []
  dane = json.loads(trafione.to_crs(4326).to_json(drop_id=True))
  for obiekt in dane["features"]:
    obiekt["geometry"]["coordinates"] = zaokraglij(obiekt["geometry"]["coordinates"])
    obiekt["properties"] = {"warstwa": "dzialki"}
  postep("    {:<18} {:>5} obiektow".format("dzialki", len(dane["features"])))
  return dane["features"]


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
      # Usluga WFS EGiB zapisuje braki jako LITERAL "None", nie jako pusta
      # wartosc — bez tego w popupie wychodzi "kondygnacje: None nadziemne".
      wlasciwosci = {k: v for k, v in obiekt["properties"].items()
                     if v is not None and v != "" and v != "None"}
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

  korytarze, powierzchnie = {}, {}

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

    zbior = warstwy_wariantu(wariant)
    korytarz = shapely.union_all(warstwy.geometry.values)
    zbior["features"].extend(warstwy_kontekstowe(korytarz))
    rozmiar = zapisz_json("{}/wariant-{}.geojson".format(KATALOG, wariant), zbior)

    # Dzialki osobno i wczytywane leniwie: sa najwieksza warstwa, a do pytania
    # "czy moj dom jest zajety" niepotrzebne. Trzymanie ich w glownym pliku
    # podnosilo wejscie na strone z ~200 kB do ~460 kB.
    dzialki = warstwa_dzialek(wariant, korytarz)
    if dzialki:
      rozmiar += zapisz_json(
          "{}/wariant-{}-dzialki.geojson".format(KATALOG, wariant),
          {"type": "FeatureCollection", "features": dzialki})
    razem += rozmiar
    print("  wariant {}: {:.0f} kB".format(wariant, rozmiar / 1024))

  print("\nIndeks wyszukiwarki (promien {} m):".format(PROMIEN_INDEKSU))
  wiersze = indeks_adresow(korytarze, powierzchnie)
  rozmiar = zapisz_json("{}/adresy-index.json".format(KATALOG), {
      "warianty": consts.VARIANTS,
      "progi": consts.STREFY,
      "promien": PROMIEN_INDEKSU,
      "adresy": wiersze,
  })
  razem += rozmiar
  print("  {} adresow, {:.0f} kB".format(len(wiersze), rozmiar / 1024))
  print("\nRazem {:.1f} MB w {}/".format(razem / 1048576, KATALOG))
