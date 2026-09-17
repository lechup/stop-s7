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
# Miary terenowe do panelu. Czytamy je wprost z podsumowanie.csv, zeby mapa
# nie mogla pokazac czegos innego niz raport — to ten sam wynik, nie drugie
# liczenie.
MIARY_DO_PANELU = [
    ("działki", "działki", None),
    ("zajęte [ha]", "zajęta powierzchnia", "ha"),
    ("łącznice [ha]", "łącznice węzłów poza śladem", "ha"),
    ("osuwiska [ha]", "osuwiska", "ha"),
    ("osuwisko aktywne ciągle [ha]", "— aktywne ciągle", "ha"),
    ("osuwisko aktywne okresowo [ha]", "— aktywne okresowo", "ha"),
    ("osuwisko nieaktywne [ha]", "— nieaktywne", "ha"),
    ("ruchy masowe [ha]", "obszary zagrożone ruchami mas", "ha"),
    ("tereny zalewowe [ha]", "tereny zalewowe", "ha"),
    ("obszary chronione [ha]", "obszary chronione", "ha"),
]
# Warstwa na mapie -> kolumna, ktora pokazujemy przy jej przelaczniku.
MIARA_WARSTWY = {
    "osuwiska": "osuwiska [ha]",
    "ruchy_masowe": "ruchy masowe [ha]",
    "powodz": "tereny zalewowe [ha]",
    "chronione": "obszary chronione [ha]",
    "dzialki": "działki",
    "lacznice": "łącznice [ha]",
}


def zapisz_miary():
  """Miary terenowe wszystkich wariantow w jednym malym pliku."""
  import pandas as pd
  sciezka = "{}/podsumowanie.csv".format(functions.KATALOG_WYNIKOW)
  if not os.path.exists(sciezka):
    return 0
  tabela = pd.read_csv(sciezka)
  wynik = {"kolejnosc": [[k, o, j] for k, o, j in MIARY_DO_PANELU],
           "przy_warstwie": MIARA_WARSTWY, "warianty": {}}
  for _, wiersz in tabela.iterrows():
    dane = {}
    for kolumna, _opis, _jedn in MIARY_DO_PANELU:
      if kolumna in wiersz and pd.notna(wiersz[kolumna]):
        dane[kolumna] = float(wiersz[kolumna])
    wynik["warianty"][wiersz["wariant"]] = dane
  return zapisz_json("{}/miary.json".format(KATALOG), wynik)


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
  # Zabudowana czy nie — z obrysow EGiB. Rozroznienie jest istotne: wywlaszczenie
  # dzialki z domem to co innego niz pola, choc jedno i drugie boli wlasciciela.
  budynki = functions.wczytaj_budynki()
  z_budynkiem = set()
  if budynki is not None and len(budynki):
    trafienia = budynki.sindex.query(trafione.geometry.values, predicate="intersects")
    z_budynkiem = set(trafienia[0].tolist())

  dane = json.loads(trafione.to_crs(4326).to_json(drop_id=True))
  for i, (obiekt, (_, rekord)) in enumerate(zip(dane["features"], trafione.iterrows())):
    obiekt["geometry"]["coordinates"] = zaokraglij(obiekt["geometry"]["coordinates"])
    obiekt["properties"] = {
        "warstwa": "dzialki",
        "teryt": rekord.get("teryt") or "",
        "obreb": rekord.get("obreb") or "",
        "nr": rekord.get("nr_dzialki") or "",
        "zab": 1 if i in z_budynkiem else 0,
    }
  postep("    {:<18} {:>5} obiektow".format("dzialki", len(dane["features"])))
  return dane["features"]


# Kilometraz podajemy tylko dla wariantow, ktore obiekt faktycznie dotycza —
# dalej jest bez znaczenia, a indeks by spuchl.
PROMIEN_KILOMETRAZU = 200

_kilometraz = {}


def punkty_kilometrazu(wariant):
  """Punkty kilometrazu co 100 m wraz z etykieta (np. '7+300')."""
  import geopandas as gpd
  if wariant not in _kilometraz:
    try:
      gdf = gpd.read_file("warianty/wariant-{}.gpkg".format(wariant),
                          layer="kilometraz_100m").to_crs(consts.CRS_METRYCZNY)
      gdf = gdf[gdf["Text"].notna()]
      _kilometraz[wariant] = gdf.reset_index(drop=True)
    except Exception:
      _kilometraz[wariant] = None
  return _kilometraz[wariant]


def dopisz_kilometraz(geometrie, wariant, wartosci, w_zasiegu):
  """Dla obiektow w zasiegu dopisuje etykiete najblizszego slupka kilometrazu."""
  import geopandas as gpd
  slupki = punkty_kilometrazu(wariant)
  if slupki is None or slupki.empty:
    return
  indeksy = [i for i, blisko in enumerate(w_zasiegu) if blisko]
  if not indeksy:
    return
  wybrane = gpd.GeoDataFrame(geometry=[geometrie[i] for i in indeksy],
                             crs=consts.CRS_METRYCZNY)
  pary = gpd.sjoin_nearest(wybrane, slupki[["Text", "geometry"]], how="inner")
  pary = pary[~pary.index.duplicated()]
  for pozycja, etykieta in zip(pary.index, pary["Text"]):
    wartosci[indeksy[pozycja]] = str(etykieta)


def indeks_dzialek(korytarze, postep=print):
  """Dzialki w promieniu PROMIEN_INDEKSU od ktoregokolwiek korytarza.

  Zasieg jest szerszy niz samo przeciecie z rozmyslu: dzialka bez zabudowy nie
  ma adresu, wiec jej wlasciciel nie znajdzie sie w wyszukiwarce adresow i bez
  tego nie mialby zadnego sposobu, zeby cokolwiek sprawdzic.

  Wartosc na wariant kodujemy jedna liczba, zeby indeks nie spuchl:
    dodatnia  — procent dzialki zajety przez korytarz,
    zero      — korytarz ja tyka, ale ponizej 1%,
    ujemna    — odleglosc od korytarza w metrach.
  """
  import geopandas as gpd
  zebrane = {}
  for wariant, korytarz in korytarze.items():
    gdf = gpd.read_file("warianty/wariant-{}.gpkg".format(wariant), layer="dzialki")
    gdf = gdf.to_crs(consts.CRS_METRYCZNY)
    gdf["geometry"] = shapely.make_valid(gdf.geometry.values)

    obszar = shapely.buffer(korytarz, PROMIEN_INDEKSU)
    bliskie = gdf.iloc[sorted(set(
        gdf.sindex.query(obszar, predicate="intersects")))].copy()
    if bliskie.empty:
      continue

    # Odleglosc liczymy do czesci korytarza, nie do calosci — drzewo STR odsiewa
    # wtedy dalekie czesci zamiast porownywac kazda dzialke z cala geometria.
    czesci = gpd.GeoDataFrame(
        geometry=list(shapely.get_parts(korytarz)), crs=consts.CRS_METRYCZNY)
    pary = gpd.sjoin_nearest(bliskie, czesci, distance_col="_odl", how="inner")
    pary = pary.sort_values("_odl").groupby(level=0).first()
    bliskie["_odl"] = pary["_odl"].reindex(bliskie.index)

    kilometraze = [None] * len(bliskie)
    dopisz_kilometraz(list(bliskie.geometry.values), wariant, kilometraze,
                      [o <= PROMIEN_KILOMETRAZU for o in bliskie["_odl"]])

    srodki = gpd.GeoSeries(bliskie.geometry.representative_point(),
                           crs=consts.CRS_METRYCZNY).to_crs(4326)
    for pozycja, ((_, rekord), punkt) in enumerate(zip(bliskie.iterrows(), srodki)):
      pole = float(rekord.get("pow_m2") or 0)
      odleglosc = float(rekord["_odl"] or 0)
      if odleglosc > 0:
        wartosc = -round(odleglosc)
      else:
        zajete = shapely.area(shapely.intersection(rekord.geometry, korytarz))
        wartosc = round(100 * zajete / pole) if pole else 0
      wpis = zebrane.setdefault(rekord.get("teryt") or "", [
          tekst(rekord.get("obreb")),
          tekst(rekord.get("nr_dzialki")),
          tekst(rekord.get("gmina")),
          round(pole),
          round(punkt.x, MIEJSC), round(punkt.y, MIEJSC),
          {}, {},
      ])
      wpis[6][wariant] = wartosc
      if kilometraze[pozycja]:
        wpis[7][wariant] = kilometraze[pozycja]
    postep("    {}: {} działek".format(wariant, len(bliskie)))
  return zebrane


def warstwy_wariantu(wariant):
  """Warstwy jednego wariantu w jednym GeoJSON-ie, z polem 'warstwa'."""
  sciezka = "raporty/wariant-{}-slad.gpkg".format(wariant)
  obiekty = []
  for warstwa in ("korytarz", "lacznice", "budynki", "adresy"):
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
  punkty = []
  for (_, rekord), punkt_wgs in zip(adresy.iterrows(), wgs.geometry):
    punkt = rekord.geometry
    punkty.append(punkt)
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
        {},
    ])

  # Kilometraz liczymy hurtem na wariant: 14 tys. adresow razy szesc wariantow
  # to za duzo, zeby pytac o kazdy obiekt osobno.
  for numer, wariant in enumerate(consts.VARIANTS):
    w_zasiegu = [wiersz[6][numer][0] <= PROMIEN_KILOMETRAZU
                 for wiersz in wiersze]
    etykiety = [None] * len(wiersze)
    dopisz_kilometraz(punkty, wariant, etykiety, w_zasiegu)
    for wiersz, etykieta in zip(wiersze, etykiety):
      if etykieta:
        wiersz[7][wariant] = etykieta
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

  print("\nIndeks działek:")
  wpisy = indeks_dzialek(korytarze)
  rozmiar = zapisz_json("{}/dzialki-index.json".format(KATALOG), {
      "warianty": consts.VARIANTS,
      "promien": PROMIEN_INDEKSU,
      "dzialki": [[teryt] + dane for teryt, dane in sorted(wpisy.items())],
  })
  razem += rozmiar
  print("  {} działek, {:.0f} kB".format(len(wpisy), rozmiar / 1024))

  rozmiar = zapisz_miary()
  if rozmiar:
    razem += rozmiar
    print("\nMiary terenowe do panelu: {:.0f} kB".format(rozmiar / 1024))

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
