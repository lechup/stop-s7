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

# Powyzej tylu trafien --adres skraca wydruk do jednej linii na adres.
SZCZEGOLOWO_DO = 5

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


def policz(wariant, postep=None):
  """Liczy rozklad adresow wzgledem korytarza drogi.

  Korytarz dzieli sie na dwie czesci liczone osobno:
    - slad powierzchniowy — droga na powierzchni,
    - pas nad tunelem — teren rozkopany, jesli tunel budowany jest odkrywkowo.
  Metoda dokladna sama z siebie zostawia nad tunelem dziure (nie ma tam linii
  skarp), a uproszczona buforuje os takze pod tunelem — rozdzielenie sprowadza
  obie metody do tej samej definicji.

  Zwraca (GeoDataFrame adresow, warstwy korytarza, czy slad jest szacowany)."""
  nazwy = geometria.nazwy_warstw(wariant)
  slad_pelny, szacowany = geometria.slad_drogi(wariant, postep)
  if slad_pelny is None:
    return None, None, False

  pas = geometria.pas_tunelu(wariant, nazwy)
  if pas is None:
    powierzchnia, korytarz = slad_pelny, slad_pelny
  else:
    powierzchnia = shapely.difference(slad_pelny, pas)
    korytarz = shapely.union_all([slad_pelny, pas])

  warstwy = {"powierzchnia": powierzchnia, "tunel": pas, "korytarz": korytarz}

  adresy = wczytaj_adresy(korytarz)
  if adresy.empty:
    return adresy.assign(odleglosc_m=[], strefa=[]), warstwy, szacowany

  # Odleglosc liczymy do poszczegolnych czesci korytarza, nie do calosci —
  # drzewo STR odsiewa wtedy dalekie czesci zamiast porownywac kazdy punkt
  # z cala, skomplikowana geometria.
  czesci = gpd.GeoDataFrame(
      geometry=list(shapely.get_parts(korytarz)), crs=consts.CRS_METRYCZNY)

  pary = gpd.sjoin_nearest(
      adresy, czesci, max_distance=float(max(consts.STREFY)),
      distance_col="odleglosc_m", how="inner")
  if pary.empty:
    return adresy.iloc[0:0].assign(odleglosc_m=[], strefa=[]), warstwy, szacowany

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
  return wynik, warstwy, szacowany


def podsumuj(wariant, adresy, szacowany=False):
  """Wiersz podsumowania: strefy rozlaczne + kolumny narastajace."""
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
  wiersz["szacunek"] = "tak" if szacowany else ""
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


def zapisz_liste_rozbiorek():
  """Czytelna lista adresow do rozbiorki, pogrupowana po miejscowosciach.

  Sklada sie z plikow wariant-*-rozbiorka.csv lezacych na dysku, nie z danych
  w pamieci — dzieki temu jest kompletna takze wtedy, gdy przeliczany byl
  tylko jeden wariant."""
  sciezka_pods = "{}/podsumowanie.csv".format(KATALOG_WYNIKOW)
  szacunki = {}
  if os.path.exists(sciezka_pods):
    pods = pd.read_csv(sciezka_pods).fillna({"szacunek": ""})
    szacunki = dict(zip(pods["wariant"], pods["szacunek"] == "tak"))

  L = ["# Adresy przeznaczone do rozbiorki", ""]
  L.append("Punkty adresowe lezace w sladzie drogi lub w pasie wykopu nad tunelem")
  L.append("budowanym metoda odkrywkowa. Zrodlo: PRG (GUGiK), stan z danych wejsciowych.")
  L.append("")
  for wariant in consts.VARIANTS:
    plik = "{}/wariant-{}-rozbiorka.csv".format(KATALOG_WYNIKOW, wariant)
    if not os.path.exists(plik):
      continue
    adresy = pd.read_csv(plik)
    szacowany = szacunki.get(wariant, False)
    L.append("## Wariant {}{}".format(wariant, " — SZACUNEK" if szacowany else ""))
    L.append("")
    if szacowany:
      L.append("> Materialy nie zawieraja dla tego wariantu warstw skarp. Slad")
      L.append("> policzono z samego pobocza, poszerzonego o sredni margines")
      L.append("> {:.1f} m na strone, zmierzony na pozostalych wariantach.".format(
          consts.MARGINES_SKARP))
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


def generate(warianty=None, zapisz_slad=True, postep=print):
  warianty = warianty or consts.VARIANTS
  os.makedirs(KATALOG_WYNIKOW, exist_ok=True)

  podsumowania = []
  for wariant in warianty:
    postep("Wariant {}:".format(wariant))
    adresy, warstwy, szacowany = policz(wariant, postep)
    if adresy is None:
      postep("  pomijam — brak warstw opisujacych droge")
      continue

    podstawa = "{}/wariant-{}".format(KATALOG_WYNIKOW, wariant)
    adresy.drop(columns="geometry").to_csv(podstawa + "-adresy.csv", index=False)

    # Lista do rozbiorki: slad powierzchniowy + pas odkrywki nad tunelem.
    rozbiorka = adresy[adresy["strefa"].isin([W_SLADZIE, NAD_TUNELEM])]
    rozbiorka = rozbiorka.assign(
        _klucz=rozbiorka["NUMER_PORZ"].map(_klucz_numeru)).sort_values(
        ["NAZWA_MSC", "NAZWA_ULC", "_klucz"], na_position="first").drop(
        columns="_klucz")
    rozbiorka.drop(columns="geometry").to_csv(podstawa + "-rozbiorka.csv", index=False)

    if zapisz_slad:
      rodzaje, geom = [], []
      for nazwa in ("powierzchnia", "tunel"):
        if warstwy.get(nazwa) is not None and not shapely.is_empty(warstwy[nazwa]):
          rodzaje.append(nazwa)
          geom.append(warstwy[nazwa])
      gpd.GeoDataFrame({"rodzaj": rodzaje}, geometry=geom,
                       crs=consts.CRS_METRYCZNY).to_file(
          podstawa + "-slad.gpkg", driver="GPKG")

    wiersz = podsumuj(wariant, adresy, szacowany)
    podsumowania.append(wiersz)
    postep("  do rozbiorki {} ({} w sladzie + {} nad tunelem), ≤200 m {}{}".format(
        wiersz[DO_ROZBIORKI], wiersz[W_SLADZIE], wiersz[NAD_TUNELEM],
        wiersz["≤{} m".format(consts.STREFY[-1])],
        "  [SZACUNEK]" if szacowany else ""))

  if not podsumowania:
    return None
  tabela = pd.DataFrame(podsumowania)

  # Przy liczeniu podzbioru wariantow dopisujemy sie do istniejacego
  # podsumowania, zamiast je zastapic — inaczej "--wariant B" kasowalby
  # z tabeli wyniki pozostalych wariantow.
  sciezka = "{}/podsumowanie.csv".format(KATALOG_WYNIKOW)
  if os.path.exists(sciezka) and len(warianty) < len(consts.VARIANTS):
    stara = pd.read_csv(sciezka).fillna({"szacunek": ""})
    stara = stara[~stara["wariant"].isin(tabela["wariant"])]
    tabela = pd.concat([stara, tabela], ignore_index=True)
  tabela = tabela.sort_values("wariant").reset_index(drop=True)
  tabela.to_csv(sciezka, index=False)
  zapisz_liste_rozbiorek()
  postep("\n" + tabela.to_string(index=False))
  if any(w["szacunek"] for w in podsumowania):
    postep("\n[SZACUNEK] — brak warstw skarp w materialach; slad z pobocza"
           " poszerzony o {:.1f} m na strone.".format(consts.MARGINES_SKARP))
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

  gdf = gpd.read_file(ADRESY, columns=KOLUMNY, where=warunek)
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
    warstwy = gpd.read_file("{}/wariant-{}-slad.gpkg".format(KATALOG_WYNIKOW, wariant))
    powierzchnia = warstwy[warstwy["rodzaj"] == "powierzchnia"]
    korytarze[wariant] = (
        shapely.union_all(warstwy.geometry.values),
        shapely.union_all(powierzchnia.geometry.values) if not powierzchnia.empty else None,
    )

  szacunki = {}
  sciezka = "{}/podsumowanie.csv".format(KATALOG_WYNIKOW)
  if os.path.exists(sciezka):
    pods = pd.read_csv(sciezka).fillna({"szacunek": ""})
    szacunki = dict(zip(pods["wariant"], pods["szacunek"] == "tak"))

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
        postep("  {:<9} {:>13.1f}m {:>15.1f}m   {}{}".format(
            wariant, od_korytarza,
            od_powierzchni if od_powierzchni is not None else float("nan"),
            strefa, "  [SZACUNEK]" if szacunki.get(wariant) else ""))
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
