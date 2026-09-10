import re

GENERATE_CHOICE = "generate"
DEBUG_CHOICE = "debug"

VARIANTS = ["A", "B", "C", "D", "E", "F"]

# Nazwy warstw w plikach GML sa niespojne miedzy wariantami: w A skarpy to
# "part_aa___2_", w C i D "skarpy_part_aa___2_", w E "2part_aa", a w E znika
# tez sufiks "___2_" (jest "pobocze_23" zamiast "pobocze_25___2_").
# Zamiast wypisywac je recznie dla kazdego wariantu, dopasowujemy wzorcem.
# Inwentarz wszystkich warstw: warstwy.md
WZORCE = {
    "os":       r"^otrasyS7_\d+(___2_)?$",
    "os_bdi":   r"^otrasyBDI_\d+(___2_)?$",
    "os_tunel": r"^otrasy(S7|BDI)wtunelu_\d+(___2_)?$",
    "jezdnia":  r"^pobocze_\d+(___2_)?$",
    "skarpy":   r"^\d*(skarpy_)?part_[a-z]{2}(___2_)?$",
    "tunele":   r"^projektowanetunele_\d+(___2_)?$",
    "estakady": r"^projektowaneestakadyimosty_\d+(___2_)?$",
    "mop":      r"^proponowanalokalizacjaMOP_\d+(___2_)?$",
    # Gotowe bufory osi policzone przez autorow materialow — sluza za
    # niezalezny punkt kontrolny dla naszych wynikow (patrz funkcje.kontrola).
    "bufor200": r"^(otrasyS7_\d+|trasa)\.json$",
    "bufor500": r"^(otrasyS7_\d+|trasa)\.json___2_$",
}

# Warstwy "pobocze" i "skarpy" obejmuja zarowno S7, jak i BDI, wiec metoda
# uproszczona buforuje obie osie — inaczej porownywalaby inny zakres drogi
# niz metoda dokladna (BDI to 4,24 km przy 19,32 km S7 w wariancie A).
OSIE = ["os", "os_bdi"]

# Progi stref odlegloci od sladu drogi [m].
STREFY = [20, 30, 50, 200]

# Sredni margines skarp na jedna strone drogi [m] — o tyle zajecie terenu
# jest szersze niz sam pas jezdni. Zmierzone na wariantach, ktore maja warstwy
# skarp (A, C, D, E, F): +8,7 / +9,2 / +5,3 / +5,6 / +9,6 m.
#
# Sluzy wylacznie do doszacowania wariantu B, ktoremu w materialach brakuje
# warstw skarp — jego slad liczony jest z samego pobocza i poszerzany o te
# wartosc. Wynik jest SZACUNKIEM, oznaczonym w raporcie; rozrzut zrodlowy
# oznacza niepewnosc rzedu +/- 2 m szerokosci sladu.
# Przeliczenie: ./uruchom.sh --mode margines
MARGINES_SKARP = 7.7

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


def dopasuj(nazwy, rola):
  """Zwraca nazwy warstw pelniacych dana role."""
  wzorzec = WZORCE[rola]
  return [n for n in nazwy if re.match(wzorzec, n)]
