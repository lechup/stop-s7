import argparse

import consts
import functions

parser = argparse.ArgumentParser(
    description="Statystyki S7 — ile adresow lezy w sladzie drogi i w strefach od niego."
)
parser.add_argument(
    "--mode",
    choices=[consts.GENERATE_CHOICE, consts.DEBUG_CHOICE],
    default=consts.GENERATE_CHOICE,
    help="'generate' liczy raporty, 'debug' wypisuje warstwy w plikach GML"
)
parser.add_argument(
    "--wariant",
    action="append",
    choices=consts.VARIANTS,
    help="Ogranicz do wybranych wariantow (mozna podac wielokrotnie); domyslnie wszystkie"
)
parser.add_argument(
    "--metoda",
    action="append",
    choices=consts.METODY,
    help="'dokladna' — obszar miedzy skarpami, 'uproszczona' — bufor osi {} m; "
         "domyslnie obie".format(consts.SZEROKOSC_UPROSZCZONA)
)
parser.add_argument(
    "--bez-sladu",
    action="store_true",
    help="Nie zapisuj plikow GPKG ze sladem drogi"
)

if __name__ == "__main__":
    args = parser.parse_args()

    if args.mode == consts.DEBUG_CHOICE:
        functions.debug()
    else:
        functions.generate(
            warianty=args.wariant,
            metody=args.metoda,
            zapisz_slad=not args.bez_sladu,
        )
