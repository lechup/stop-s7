"""Statystyki S7 — ile adresow lezy w sladzie drogi i w strefach od niego.

Copyright (C) 2026 Leszek Piatek

Ten program jest wolnym oprogramowaniem: mozesz go rozpowszechniac i/lub
modyfikowac na warunkach Licencji AGPL GNU w wersji 3, opublikowanej przez
Free Software Foundation. Program rozpowszechniany jest w nadziei, ze bedzie
uzyteczny, ale BEZ JAKIEJKOLWIEK GWARANCJI. Szczegoly w pliku LICENSE.
"""

import argparse

import consts
import functions

parser = argparse.ArgumentParser(
    description="Statystyki S7 — ile adresow lezy w sladzie drogi i w strefach od niego."
)
parser.add_argument(
    "--mode",
    choices=[consts.GENERATE_CHOICE, consts.DEBUG_CHOICE, "dane"],
    default=consts.GENERATE_CHOICE,
    help="'generate' liczy raporty, 'debug' wypisuje warstwy w plikach GML, "
         "'dane' pokazuje na jakich danych skrypt liczy"
)
parser.add_argument(
    "--wariant",
    action="append",
    choices=consts.VARIANTS,
    help="Ogranicz do wybranych wariantow (mozna podac wielokrotnie); domyslnie wszystkie"
)
parser.add_argument(
    "--adres",
    metavar="ZAPYTANIE",
    help="Sprawdz pojedynczy adres we wszystkich wariantach, np. --adres \"Osterwy 41P\" "
         "albo --adres \"Golkowice 116\". Korzysta z zapisanych sladow"
)
parser.add_argument(
    "--tylko-miary",
    action="store_true",
    help="Przelicz miary (dzialki, osuwiska, tereny zalewowe, obszary chronione) "
         "z zapisanych sladow, bez skladania ich od nowa — minuta zamiast "
         "czterdziestu. Po zmianie sposobu liczenia SLADU uruchom pelny raport"
)
parser.add_argument(
    "--bez-sladu",
    action="store_true",
    help="Nie zapisuj plikow GPKG ze sladem drogi"
)

if __name__ == "__main__":
    args = parser.parse_args()

    if args.adres:
        functions.sprawdz_adres(args.adres)
    elif args.mode == consts.DEBUG_CHOICE:
        functions.debug()
    elif args.mode == "dane":
        functions.informacje_o_danych()
    elif args.tylko_miary:
        functions.przelicz_miary(warianty=args.wariant)
    else:
        functions.generate(
            warianty=args.wariant,
            zapisz_slad=not args.bez_sladu,
        )
