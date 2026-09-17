"""Budowanie sladu drogi z warstw wariantu.

Warstwy opisujace droge to linie (krawedzie jezdni i skarpy), a nie poligony,
wiec "slad drogi" trzeba z nich dopiero zlozyc. Robi to domkniecie
morfologiczne: bufor dodatni skleja rownolegle linie w jedna bryle, a bufor
ujemny sciaga ja z powrotem do pierwotnego zasiegu. Pojedyncza linia bez
sasiadow znika w tym procesie, wiec zostaje tylko obszar faktycznie otoczony
liniami — czyli teren zajety pod droge.

Do tego dochodza estakady, ktore sa juz poligonami: tam, gdzie droga idzie po
estakadzie, nie ma nasypu ani linii skarp, wiec samo domkniecie zostawialoby
w sladzie dziure.

Dane pochodza z serwisow konsultacyjnych STES i sa skladane przez
pobierz_warianty.py do GPKG, w ktorym nazwa warstwy rowna sie roli.

UWAGA na pamiec: buforowanie calej sieci linii naraz (kilkanascie tysiecy
odcinkow, ponad 150 km) potrafi zjesc kilkanascie GB. Dlatego liczymy
kafelkami i laczymy wyniki narastajaco. Nie zmieniaj tego na operacje globalna.
"""

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import box

import consts


def sciezka(wariant):
  return "warianty/wariant-{}.gpkg".format(wariant)


def nazwy_warstw(wariant):
  return [nazwa for nazwa, _typ in pyogrio.list_layers(sciezka(wariant))]


def wczytaj(wariant, rola, nazwy=None):
  """Wczytuje warstwe danej roli w ukladzie metrycznym.

  Zwraca GeoSeries (pusta, jesli wariant takiej warstwy nie ma — np. D, E i F
  nie maja drogi towarzyszacej BDI)."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  if rola not in nazwy:
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)
  gdf = gpd.read_file(sciezka(wariant), layer=rola)
  if gdf.empty or gdf.geometry.isna().all():
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)
  return gdf.geometry.dropna().to_crs(consts.CRS_METRYCZNY)


def osie(wariant, nazwy=None):
  """Osie wszystkich drog objetych wariantem (S7 + BDI, jesli wystepuje)."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  kawalki = [wczytaj(wariant, rola, nazwy) for rola in consts.OSIE]
  kawalki = [k for k in kawalki if len(k)]
  if not kawalki:
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)
  return gpd.GeoSeries(pd.concat(kawalki, ignore_index=True),
                       crs=consts.CRS_METRYCZNY)


def _kafelki(granice):
  """Dzieli prostokat na kafelki o boku BOK_KAFELKA."""
  minx, miny, maxx, maxy = granice
  bok = consts.BOK_KAFELKA
  x = minx
  while x < maxx:
    y = miny
    while y < maxy:
      yield box(x, y, min(x + bok, maxx), min(y + bok, maxy))
      y += bok
    x += bok


def slad_drogi(wariant, postep=None):
  """Obszar faktycznie zajety pod droge: jezdnia, skarpy i estakady.

  Linie (jezdnia, skarpy) skladane sa domknieciem morfologicznym, estakady
  dochodza wprost, bo sa juz poligonami. Bez nich slad mialby dziury tam,
  gdzie droga idzie po estakadzie i nie ma nasypu."""
  nazwy = nazwy_warstw(wariant)
  linie = [wczytaj(wariant, r, nazwy) for r in consts.WARSTWY_SLADU
           if r != "estakady"]
  linie = [k for k in linie if len(k)]
  if not linie:
    return None

  linie = gpd.GeoSeries(pd.concat(linie, ignore_index=True),
                        crs=consts.CRS_METRYCZNY)
  linie = linie[~linie.is_empty & linie.notna()]
  # Upraszczanie przed buforowaniem tnie liczbe wierzcholkow kilkukrotnie.
  linie = linie.simplify(consts.TOLERANCJA)

  drzewo = linie.sindex
  r = consts.PROMIEN_DOMKNIECIA
  czesci = []
  zebrane = []
  kafelki = list(_kafelki(linie.total_bounds))

  for i, rdzen in enumerate(kafelki, 1):
    otoczka = rdzen.buffer(consts.ZAKLADKA)
    trafienia = drzewo.query(otoczka, predicate="intersects")
    if len(trafienia) == 0:
      continue

    lokalne = shapely.intersection(
        shapely.union_all(linie.iloc[trafienia].values), otoczka)
    # Domkniecie: skleja rownolegle linie, potem sciaga do pierwotnego zasiegu.
    zamkniete = shapely.buffer(lokalne, r, quad_segs=2)
    zamkniete = shapely.simplify(zamkniete, consts.TOLERANCJA)
    zamkniete = shapely.buffer(zamkniete, -r, quad_segs=2)
    # Tylko rdzen, zeby zakladka nie liczyla sie dwa razy.
    zamkniete = shapely.intersection(zamkniete, rdzen)

    if not shapely.is_empty(zamkniete) and shapely.area(zamkniete) > 0:
      czesci.append(zamkniete)

    # Scalanie narastajaco — trzyma liste krotka i pamiec plaska.
    if len(czesci) >= 20:
      zebrane.append(shapely.union_all(czesci))
      czesci = []

    if postep and i % 25 == 0:
      postep("    kafelek {}/{}".format(i, len(kafelki)))

  if czesci:
    zebrane.append(shapely.union_all(czesci))
  if not zebrane:
    return None
  slad = shapely.union_all(zebrane)

  # Estakady sa poligonami — dochodza wprost. make_valid, bo geometria
  # z eksportu CAD-owego bywa topologicznie niepoprawna.
  estakady = wczytaj(wariant, "estakady", nazwy)
  if len(estakady):
    slad = shapely.union_all(
        [slad, shapely.union_all(shapely.make_valid(estakady.values))])
  return slad


def lacznice(wariant, nazwy=None):
  """Pas lacznic wezlow (None, gdy wariant ich nie ma).

  Celowo NIE wchodzi do sladu drogi: szerokosc jest zalozona (patrz
  consts.SZEROKOSC_LACZNICY), a cala reszta wyliczenia opiera sie wylacznie
  na tym, co narysowano w materialach. Liczymy to osobno, zeby bylo widac,
  o ile slad zaniza zajecie terenu przy wezlach."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  linie = wczytaj(wariant, consts.WARSTWA_LACZNIC, nazwy)
  if linie is None or not len(linie):
    return None
  return shapely.buffer(shapely.union_all(linie.values),
                        consts.SZEROKOSC_LACZNICY)


def pas_tunelu(wariant, nazwy=None):
  """Pas wykopu nad odcinkami tunelowymi (None, gdy wariant nie ma tuneli).

  Samo domkniecie zostawia nad tunelem dziure, bo nie ma tam linii skarp —
  co jest poprawne dla tunelu drazonego, ale nie dla odkrywki, gdzie teren
  jest rozkopany na calej szerokosci."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  kawalki = [wczytaj(wariant, rola, nazwy) for rola in consts.OSIE_TUNELI]
  kawalki = [k for k in kawalki if len(k)]
  if not kawalki:
    return None
  osie_tuneli = pd.concat(kawalki, ignore_index=True)
  return shapely.buffer(
      shapely.union_all(osie_tuneli.values), consts.SZEROKOSC_ODKRYWKI)
