"""Budowanie sladu drogi z warstw GML wariantu.

Warstwy opisujace droge to linie (krawedzie jezdni i skarpy), a nie poligony,
wiec "slad drogi" trzeba z nich dopiero zlozyc. Robi to domkniecie
morfologiczne: bufor dodatni skleja rownolegle linie w jedna bryle, a bufor
ujemny sciaga ja z powrotem do pierwotnego zasiegu. Pojedyncza linia bez
sasiadow znika w tym procesie, wiec zostaje tylko obszar faktycznie otoczony
liniami — czyli teren zajety pod droge.

UWAGA na pamiec: buforowanie calej sieci linii naraz (16 tys. odcinkow,
160 km) potrafi zjesc kilkanascie GB. Dlatego liczymy kafelkami i laczymy
wyniki narastajaco. Nie zmieniaj tego na operacje globalna.
"""

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import box

import consts


def sciezka(wariant):
  return "warianty/wariant{}.gml".format(wariant)


def nazwy_warstw(wariant):
  return [nazwa for nazwa, _typ in pyogrio.list_layers(sciezka(wariant))]


def wczytaj(wariant, rola, nazwy=None):
  """Wczytuje wszystkie warstwy pelniace dana role, w ukladzie metrycznym.

  Zwraca GeoSeries (pusta, jesli wariant nie ma takich warstw)."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  pasujace = consts.dopasuj(nazwy, rola)
  if not pasujace:
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)

  kawalki = []
  for warstwa in pasujace:
    gdf = gpd.read_file(sciezka(wariant), layer=warstwa)
    if gdf.empty or gdf.geometry.isna().all():
      continue
    kawalki.append(gdf.geometry.dropna().to_crs(consts.CRS_METRYCZNY))
  if not kawalki:
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)
  return gpd.GeoSeries(pd.concat(kawalki, ignore_index=True), crs=consts.CRS_METRYCZNY)


def osie(wariant, nazwy=None):
  """Osie wszystkich drog objetych wariantem (S7 + BDI)."""
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  kawalki = [wczytaj(wariant, rola, nazwy) for rola in consts.OSIE]
  kawalki = [k for k in kawalki if len(k)]
  if not kawalki:
    return gpd.GeoSeries([], crs=consts.CRS_METRYCZNY)
  return gpd.GeoSeries(pd.concat(kawalki, ignore_index=True), crs=consts.CRS_METRYCZNY)


def ma_skarpy(wariant, nazwy=None):
  nazwy = nazwy if nazwy is not None else nazwy_warstw(wariant)
  return bool(consts.dopasuj(nazwy, "skarpy"))


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


def slad_dokladny(wariant, postep=None):
  """Obszar miedzy zewnetrznymi liniami skarp — realne zajecie terenu.

  Wymaga warstw skarp; wariant B ich nie ma (zwraca None)."""
  nazwy = nazwy_warstw(wariant)
  if not ma_skarpy(wariant, nazwy):
    return None

  linie = pd.concat(
      [wczytaj(wariant, "jezdnia", nazwy), wczytaj(wariant, "skarpy", nazwy)],
      ignore_index=True,
  )
  linie = gpd.GeoSeries(linie, crs=consts.CRS_METRYCZNY)
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
    # Domkniecie: skleja rownoleglie linie, potem sciaga do pierwotnego zasiegu.
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
  return shapely.union_all(zebrane)


def slad_uproszczony(wariant, nazwy=None):
  """Bufor osi drog o stalej szerokosci — dziala dla kazdego wariantu."""
  os_wariantu = osie(wariant, nazwy)
  if not len(os_wariantu):
    return None
  return shapely.buffer(
      shapely.union_all(os_wariantu.values), consts.SZEROKOSC_UPROSZCZONA)


def slad(wariant, metoda, postep=None):
  if metoda == consts.DOKLADNA:
    return slad_dokladny(wariant, postep)
  return slad_uproszczony(wariant)
