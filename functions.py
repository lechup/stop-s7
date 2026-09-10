"""Zliczanie punktow adresowych wzgledem sladu drogi."""

import os
import re

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
NAD_TUNELEM = "nad tunelem"
DO_ROZBIORKI = "do rozbiórki"


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


def policz(wariant, metoda, postep=None):
  """Liczy rozklad adresow wzgledem korytarza drogi.

  Korytarz dzieli sie na dwie czesci liczone osobno:
    - slad powierzchniowy — droga na powierzchni,
    - pas nad tunelem — teren rozkopany, jesli tunel budowany jest odkrywkowo.
  Metoda dokladna sama z siebie zostawia nad tunelem dziure (nie ma tam linii
  skarp), a uproszczona buforuje os takze pod tunelem — rozdzielenie sprowadza
  obie metody do tej samej definicji.

  Zwraca (GeoDataFrame adresow w zasiegu, warstwy korytarza) albo (None, None)."""
  nazwy = geometria.nazwy_warstw(wariant)
  slad_pelny = geometria.slad(wariant, metoda, postep)
  if slad_pelny is None:
    return None, None

  pas = geometria.pas_tunelu(wariant, nazwy)
  if pas is None:
    powierzchnia, korytarz = slad_pelny, slad_pelny
  else:
    powierzchnia = shapely.difference(slad_pelny, pas)
    korytarz = shapely.union_all([slad_pelny, pas])

  warstwy = {"powierzchnia": powierzchnia, "tunel": pas, "korytarz": korytarz}

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


def podsumuj(wariant, metoda, adresy):
  """Wiersz podsumowania: strefy rozlaczne + kolumny narastajace."""
  wiersz = {"wariant": wariant, "metoda": metoda}
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


def zapisz_liste_rozbiorek(rozbiorki):
  """Czytelna lista adresow do rozbiorki, pogrupowana po miejscowosciach."""
  L = ["# Adresy przeznaczone do rozbiorki", ""]
  L.append("Punkty adresowe lezace w sladzie drogi lub w pasie wykopu nad tunelem")
  L.append("budowanym metoda odkrywkowa. Zrodlo: PRG (GUGiK), stan z danych wejsciowych.")
  L.append("")
  for (wariant, metoda), adresy in sorted(rozbiorki.items()):
    L.append("## Wariant {} — metoda {}".format(wariant, metoda))
    L.append("")
    if adresy.empty:
      L.append("_Brak adresow._\n")
      continue
    L.append("Razem: **{}** adresow ({} w sladzie, {} nad tunelem).".format(
        len(adresy),
        int((adresy["strefa"] == W_SLADZIE).sum()),
        int((adresy["strefa"] == NAD_TUNELEM).sum())))
    L.append("")
    adresy = adresy.assign(_klucz=adresy["NUMER_PORZ"].map(_klucz_numeru))
    for msc, grupa in adresy.groupby("NAZWA_MSC", sort=True, dropna=False):
      grupa = grupa.sort_values(["NAZWA_ULC", "_klucz"], na_position="first")
      L.append("### {} ({})".format(msc, len(grupa)))
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


def generate(warianty=None, metody=None, zapisz_slad=True, postep=print):
  warianty = warianty or consts.VARIANTS
  metody = metody or consts.METODY
  os.makedirs(KATALOG_WYNIKOW, exist_ok=True)

  podsumowania = []
  rozbiorki = {}
  for wariant in warianty:
    for metoda in metody:
      postep("Wariant {} / metoda {}:".format(wariant, metoda))
      adresy, warstwy = policz(wariant, metoda, postep)
      if adresy is None:
        postep("  pomijam — brak warstw skarp w tym wariancie")
        continue

      podstawa = "{}/wariant-{}-{}".format(KATALOG_WYNIKOW, wariant, metoda)
      adresy.drop(columns="geometry").to_csv(podstawa + "-adresy.csv", index=False)

      # Lista do rozbiorki: slad powierzchniowy + pas odkrywki nad tunelem.
      rozbiorka = adresy[adresy["strefa"].isin([W_SLADZIE, NAD_TUNELEM])]
      rozbiorka = rozbiorka.assign(
          _klucz=rozbiorka["NUMER_PORZ"].map(_klucz_numeru)).sort_values(
          ["NAZWA_MSC", "NAZWA_ULC", "_klucz"], na_position="first").drop(
          columns="_klucz")
      rozbiorka.drop(columns="geometry").to_csv(podstawa + "-rozbiorka.csv", index=False)
      rozbiorki[(wariant, metoda)] = rozbiorka

      if zapisz_slad:
        rodzaje, geom = [], []
        for nazwa in ("powierzchnia", "tunel"):
          if warstwy.get(nazwa) is not None and not shapely.is_empty(warstwy[nazwa]):
            rodzaje.append(nazwa)
            geom.append(warstwy[nazwa])
        gpd.GeoDataFrame({"rodzaj": rodzaje}, geometry=geom,
                         crs=consts.CRS_METRYCZNY).to_file(
            podstawa + "-slad.gpkg", driver="GPKG")

      wiersz = podsumuj(wariant, metoda, adresy)
      podsumowania.append(wiersz)
      postep("  do rozbiorki {} ({} w sladzie + {} nad tunelem), ≤200 m {}".format(
          wiersz[DO_ROZBIORKI], wiersz[W_SLADZIE], wiersz[NAD_TUNELEM],
          wiersz["≤{} m".format(consts.STREFY[-1])]))

  if not podsumowania:
    return None
  zapisz_liste_rozbiorek(rozbiorki)
  tabela = pd.DataFrame(podsumowania)
  tabela.to_csv("{}/podsumowanie.csv".format(KATALOG_WYNIKOW), index=False)
  postep("\n" + tabela.to_string(index=False))
  postep("\nZapisano {}/podsumowanie.csv i {}/rozbiorka.md".format(
      KATALOG_WYNIKOW, KATALOG_WYNIKOW))
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
