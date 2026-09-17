import re

GENERATE_CHOICE = "generate"
DEBUG_CHOICE = "debug"

VARIANTS = ["A", "B", "C", "D", "E", "F"]

# Warstwy wariantow pochodza z serwisow konsultacyjnych STES (eksporty qgis2web)
# i sa skladane przez pobierz_warianty.py do GPKG o nazwach warstw rownych
# rolom — nie trzeba juz dopasowywac wzorcem, jak przy plikach GML, gdzie
# numeracja i sufiksy roznily sie miedzy wariantami.
# Inwentarz warstw: warstwy.md

# Warstwy skladajace sie na slad drogi, czyli teren faktycznie zajety.
# Estakady doszly, bo tam gdzie droga idzie po estakadzie nie ma nasypu,
# a wiec i linii skarp — slad mial w tych miejscach dziury, choc budynek
# pod projektowana estakada jest zajety tak samo jak pod nasypem.
WARSTWY_SLADU = ["jezdnia", "skarpy", "estakady"]

# Osie wszystkich drog objetych wariantem (S7 + droga towarzyszaca BDI).
OSIE = ["os", "os_bdi"]

# Osie odcinkow tunelowych.
OSIE_TUNELI = ["os_tunel", "os_tunel_bdi"]

# Progi stref odlegloci od sladu drogi [m].
STREFY = [20, 30, 50, 200]

# Polowa szerokosci wykopu nad tunelem [m]. Tunele budowane metoda odkrywkowa
# wymagaja wykopu mniej wiecej tak szerokiego jak droga na powierzchni —
# zmierzone slady maja 47,7-57,9 m szerokosci, stad 30 m w kazda strone.
# Adresy w tym pasie trafiaja do osobnej kolumny "nad tunelem", a nie do
# "w sladzie": nad tunelem drazonym budynki zostaja, nad odkrywka nie.
SZEROKOSC_ODKRYWKI = 30

# Domkniecie morfologiczne: promien dobrany kalibracja (patrz warstwy.md).
# Ponizej 20 m linie skarp sie nie domykaja i slad rozpada sie na kawalki;
# od 20 m wynik wchodzi na plaskowyz (42,0 -> 42,4 -> 42,7 m sredniej
# szerokosci dla r = 20/25/30), wiec 25 m to srodek stabilnego zakresu.
PROMIEN_DOMKNIECIA = 25

# Lacznice wezlow. Material zrodlowy rysuje je sama kreska (warstwa
# D-Plan-SchematyWezlow) — bez pary linii pobocza i bez skarp, ktore ma trasa
# glowna, wiec domkniecie morfologiczne nie ma tam czego domknac i przy wezle
# ze sladu zostaja tylko poligony estakad. Zeby dalo sie je w ogole zmierzyc,
# przyjmujemy szerokosc: 8 m od kreski w kazda strone, tyle co jednopasowa
# lacznica z poboczami. To ZALOZENIE, a nie pomiar — i dlatego lacznice nie
# wchodza do sladu drogi, tylko licza sie w osobnych kolumnach.
WARSTWA_LACZNIC = "uklad_wezlow"
SZEROKOSC_LACZNICY = 8

# Przetwarzanie kafelkami — buforowanie calej sieci linii naraz zjada
# kilkanascie GB i konczy sie ubiciem sesji przez systemd-oomd.
BOK_KAFELKA = 1000    # [m]
ZAKLADKA = 150        # [m], margines wejsciowy zeby domkniecie nie urywalo sie na krawedzi

# Upraszczanie geometrii przed buforowaniem [m] — mocno tnie liczbe
# wierzcholkow bez zauwazalnego wplywu na wynik.
TOLERANCJA = 0.5

# Uklad metryczny, w ktorym liczymy odleglosci i pola (PL-1992).
CRS_METRYCZNY = 2180


NAZWY_RODZAJOW = [
    ("OsuwiskaAktywneCiagle", "osuwisko aktywne ciągle"),
    ("OsuwiskaAktywneOkresowo", "osuwisko aktywne okresowo"),
    ("OsuwiskaNieaktywne", "osuwisko nieaktywne"),
    ("ObszaryZagrozone", "obszar zagrożony ruchami masowymi"),
    ("ParkiNarodoweOtulina", "otulina parku narodowego"),
    ("Park Narodowy", "park narodowy"),
    ("ParkiKrajobrazowe", "park krajobrazowy"),
    ("ObszaryChronionegoKrajobrazu", "obszar chronionego krajobrazu"),
    ("ObszarySpecjalnejOchrony", "Natura 2000 — obszar ptasi"),
    ("SpecjalneObszaryOchrony", "Natura 2000 — obszar siedliskowy"),
    ("ZespolyPrzyrodniczoKrajobrazowe", "zespół przyrodniczo-krajobrazowy"),
    ("StanowiskaDokumentacyjne", "stanowisko dokumentacyjne"),
    ("UzytkiEkologiczne", "użytek ekologiczny"),
    ("Rezerwaty", "rezerwat przyrody"),
]


def napraw_kodowanie(tekst):
  """Odzyskuje polskie znaki z napisu zapisanego UTF-8, a odczytanego Latin-1.

  Zrodlo ma tak popsuta czesc nazw warstw ("OsuwiskaAktywneCiÄ…gle" zamiast
  "...Ciagle"). Odwracamy przez CP1252, a nie Latin-1: w zepsutym napisie siedzi
  U+2026 ("..."), ktorego w Latin-1 nie ma, wiec odwrocenie tamtym by sie
  wysypalo. Gdy sie nie uda, zwracamy napis bez zmian."""
  for kodowanie in ("cp1252", "latin-1"):
    try:
      return tekst.encode(kodowanie).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
      continue
  return tekst


def bez_ogonkow(tekst):
  ogonki = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
  return "".join(c for c in tekst.translate(ogonki) if c.isalnum()).lower()


def nazwa_rodzaju(wartosc, domyslna):
  """Czytelna nazwa z atrybutu Layer (np. 'G-Plan-OsuwiskaNieaktywneHatch')."""
  if not wartosc:
    return domyslna
  uproszczone = bez_ogonkow(napraw_kodowanie(str(wartosc)))
  for wzorzec, nazwa in NAZWY_RODZAJOW:
    if bez_ogonkow(wzorzec) in uproszczone:
      return nazwa
  return domyslna
