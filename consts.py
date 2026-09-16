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

# Przetwarzanie kafelkami — buforowanie calej sieci linii naraz zjada
# kilkanascie GB i konczy sie ubiciem sesji przez systemd-oomd.
BOK_KAFELKA = 1000    # [m]
ZAKLADKA = 150        # [m], margines wejsciowy zeby domkniecie nie urywalo sie na krawedzi

# Upraszczanie geometrii przed buforowaniem [m] — mocno tnie liczbe
# wierzcholkow bez zauwazalnego wplywu na wynik.
TOLERANCJA = 0.5

# Uklad metryczny, w ktorym liczymy odleglosci i pola (PL-1992).
CRS_METRYCZNY = 2180
