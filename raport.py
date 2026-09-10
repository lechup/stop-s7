import argparse

import consts
import functions
import geometria

parser = argparse.ArgumentParser(
    description="Statystyki S7 — ile adresow lezy w sladzie drogi i w strefach od niego."
)
parser.add_argument(
    "--mode",
    choices=[consts.GENERATE_CHOICE, consts.DEBUG_CHOICE, "margines"],
    default=consts.GENERATE_CHOICE,
    help="'generate' liczy raporty, 'debug' wypisuje warstwy w plikach GML, "
         "'margines' przelicza sredni margines skarp (consts.MARGINES_SKARP)"
)
parser.add_argument(
    "--wariant",
    action="append",
    choices=consts.VARIANTS,
    help="Ogranicz do wybranych wariantow (mozna podac wielokrotnie); domyslnie wszystkie"
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
    elif args.mode == "margines":
        geometria.zmierz_margines(args.wariant)
    else:
        functions.generate(
            warianty=args.wariant,
            zapisz_slad=not args.bez_sladu,
        )
