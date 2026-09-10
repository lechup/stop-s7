"""Zliczanie punktow adresowych wzgledem sladu drogi."""

import os

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely

import consts
import geometria

ADRESY = "wojewodztwa-adresy/malopolska/NOWE_PRG_PunktyAdresowe_12.shp"
KOLUMNY = ["NUMER_PORZ", "NAZWA_ULC", "NAZWA_MSC", "NAZWA_GMI", "KOD_POCZT"]
KATALOG_WYNIKOW = "raporty"

W_SLADZIE = "w śladzie"


def wczytaj_adresy(obszar):
  """Czyta tylko adresy z otoczenia obszaru.

  Plik ma 856 tys. rekordow i 786 MB atrybutow — wczytywanie calosci jest
  zbedne i kosztuje kilka GB, wiec filtrujemy bbox-em juz przy odczycie."""
  minx, miny, maxx, maxy = shapely.bounds(obszar)
  m = max(consts.STREFY)
  gdf = gpd.read_file(
      ADRESY,
      bbox=(minx - m, miny - m, maxx + m, maxy + m),
      columns=KOLUMNY,
  )
  # Shapefile podaje uklad jako WKT ("ETRF2000-PL / CS92"), a nasze geometrie
  # maja go jako EPSG:2180. To ten sam uklad, ale bez ujednolicenia geopandas
  # zglasza niezgodnosc CRS przy zlaczeniach przestrzennych.
  return gdf.to_crs(consts.CRS_METRYCZNY)


def nazwy_stref():
  """Nazwy stref rozlacznych, od sladu na zewnatrz."""
  nazwy = [W_SLADZIE]
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


def policz(wariant, metoda, postep=None):
  """Liczy rozklad adresow wzgledem sladu drogi.

  Zwraca (GeoDataFrame adresow w zasiegu, slad) albo (None, None), jesli
  wariant nie ma warstw potrzebnych dla tej metody."""
  slad = geometria.slad(wariant, metoda, postep)
  if slad is None:
    return None, None

  adresy = wczytaj_adresy(slad)
  if adresy.empty:
    return adresy.assign(odleglosc_m=[], strefa=[]), slad

  # Odleglosc liczymy do poszczegolnych czesci sladu, nie do calosci —
  # drzewo STR odsiewa wtedy dalekie czesci zamiast porownywac kazdy punkt
  # z cala, skomplikowana geometria.
  czesci = gpd.GeoDataFrame(
      geometry=list(shapely.get_parts(slad)), crs=consts.CRS_METRYCZNY)

  pary = gpd.sjoin_nearest(
      adresy, czesci, max_distance=float(max(consts.STREFY)),
      distance_col="odleglosc_m", how="inner")
  if pary.empty:
    return adresy.iloc[0:0].assign(odleglosc_m=[], strefa=[]), slad

  # sjoin_nearest zwraca po wierszu na kazda remisujaca czesc sladu.
  pary = pary.sort_values("odleglosc_m").groupby(level=0).first()
  wynik = adresy.loc[pary.index].copy()
  wynik["odleglosc_m"] = pary["odleglosc_m"].round(1)

  w_sladzie = set(adresy.sindex.query(slad, predicate="contains"))
  pozycje = {idx: i for i, idx in enumerate(adresy.index)}
  wynik["strefa"] = [
      W_SLADZIE if pozycje[idx] in w_sladzie else _strefa(odl)
      for idx, odl in zip(wynik.index, wynik["odleglosc_m"])
  ]
  # Punkt tuz przy krawedzi moze miec odleglosc 0 i nie byc "wewnatrz".
  wynik["strefa"] = wynik["strefa"].fillna(nazwy_stref()[1])
  return wynik, slad


def podsumuj(wariant, metoda, adresy):
  """Wiersz podsumowania: strefy rozlaczne + kolumny narastajace."""
  wiersz = {"wariant": wariant, "metoda": metoda}
  liczby = adresy["strefa"].value_counts() if len(adresy) else {}
  for nazwa in nazwy_stref():
    wiersz[nazwa] = int(liczby.get(nazwa, 0)) if len(adresy) else 0

  narastajaco = wiersz[W_SLADZIE]
  poprzedni = 0
  for prog in consts.STREFY:
    narastajaco += wiersz["{}-{} m".format(poprzedni, prog)]
    wiersz["≤{} m".format(prog)] = narastajaco
    poprzedni = prog
  return wiersz


def kontrola(wariant):
  """Kontrola krzyzowa: adresy w gotowym buforze 200 m z materialow zrodlowych.

  Autorzy materialow dolaczyli wlasny bufor 200 m wokol osi S7. Policzenie
  adresow w nim i porownanie z nasza kolumna "≤200 m" pokazuje, czy nasze
  liczenie jest poprawne. Bufor dotyczy samej S7 (bez BDI), wiec porownujemy
  go z uproszczonym sladem liczonym tylko dla osi S7."""
  nazwy = geometria.nazwy_warstw(wariant)
  bufor = geometria.wczytaj(wariant, "bufor200", nazwy)
  if not len(bufor):
    return None
  obszar = shapely.union_all(bufor.values)
  adresy = wczytaj_adresy(obszar)
  if adresy.empty:
    return {"wariant": wariant, "w_buforze_zrodlowym": 0, "nasze_200m": 0}

  w_buforze = len(adresy.sindex.query(obszar, predicate="contains"))

  os_s7 = geometria.wczytaj(wariant, "os", nazwy)
  nasz = shapely.buffer(shapely.union_all(os_s7.values), max(consts.STREFY))
  nasze_200 = len(adresy.sindex.query(nasz, predicate="contains"))
  return {
      "wariant": wariant,
      "w_buforze_zrodlowym": w_buforze,
      "nasze_200m": nasze_200,
      "roznica_%": round(100 * (nasze_200 - w_buforze) / w_buforze, 2) if w_buforze else None,
  }


def generate(warianty=None, metody=None, zapisz_slad=True, postep=print):
  warianty = warianty or consts.VARIANTS
  metody = metody or consts.METODY
  os.makedirs(KATALOG_WYNIKOW, exist_ok=True)

  podsumowania = []
  for wariant in warianty:
    for metoda in metody:
      postep("Wariant {} / metoda {}:".format(wariant, metoda))
      adresy, slad = policz(wariant, metoda, postep)
      if adresy is None:
        postep("  pomijam — brak warstw skarp w tym wariancie")
        continue

      plik = "{}/wariant-{}-{}-adresy.csv".format(KATALOG_WYNIKOW, wariant, metoda)
      adresy.drop(columns="geometry").to_csv(plik, index=False)
      if zapisz_slad:
        gpd.GeoDataFrame(geometry=[slad], crs=consts.CRS_METRYCZNY).to_file(
            "{}/wariant-{}-{}-slad.gpkg".format(KATALOG_WYNIKOW, wariant, metoda),
            driver="GPKG")

      wiersz = podsumuj(wariant, metoda, adresy)
      podsumowania.append(wiersz)
      postep("  w śladzie {}, ≤200 m {}  →  {}".format(
          wiersz[W_SLADZIE], wiersz["≤{} m".format(consts.STREFY[-1])], plik))

  if not podsumowania:
    return None
  tabela = pd.DataFrame(podsumowania)
  tabela.to_csv("{}/podsumowanie.csv".format(KATALOG_WYNIKOW), index=False)
  postep("\n" + tabela.to_string(index=False))
  postep("\nZapisano {}/podsumowanie.csv".format(KATALOG_WYNIKOW))
  return tabela


def debug():
  """Inwentarz warstw w plikach GML — nazwy, typy, liczby obiektow."""
  for wariant in consts.VARIANTS:
    sciezka = geometria.sciezka(wariant)
    print("Wariant {} ({}):".format(wariant, sciezka))
    nazwy = geometria.nazwy_warstw(wariant)
    for nazwa in nazwy:
      info = pyogrio.read_info(sciezka, layer=nazwa)
      role = [r for r in consts.WZORCE if consts.dopasuj([nazwa], r)]
      print("  {:<46} {:<16} n={:<6} {}".format(
          nazwa, str(info.get("geometry_type")), info.get("features"),
          ",".join(role) or "-"))
    braki = [r for r in ("os", "jezdnia", "skarpy") if not consts.dopasuj(nazwy, r)]
    print("  BRAKI: {}\n".format(", ".join(braki) if braki else "brak"))
