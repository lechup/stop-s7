import argparse
import functions
import consts



parser = argparse.ArgumentParser(
    description="Statystyki S7"
)
parser.add_argument(
    "--mode",
    choices=[consts.GENERATE_CHOICE, consts.DEBUG_CHOICE],
    default=consts.GENERATE_CHOICE,
    help="Tryb działania, 'generate' generuje pliki a 'debug' pokazuje informacje dot. warstw w plikach gml"
)
args = parser.parse_args()

if args.mode == consts.GENERATE_CHOICE:
    functions.generate();
elif args.mode == consts.DEBUG_CHOICE:
    functions.debug();

