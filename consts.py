GENERATE_CHOICE = "generate"
DEBUG_CHOICE = "debug"

WAY = "trasa"
BRIDGES_TUNNELS = "tunele-i-mosty"
STOPS = "mops"

LAYERS_DICT_PER_VARIANT = {
   "A": {
      WAY: [
          "pobocze_25___2_",
          "part_aa___2_",
          "part_ab___2_",
          "part_ac___2_",
          "part_ad___2_",
      ],
      BRIDGES_TUNNELS: [
          "projektowanetunele_20___2_",
          "projektowaneestakadyimosty_21___2_"
      ],
      STOPS: [
          "proponowanalokalizacjaMOP_16___2_"
      ],
   },
   "B": {},
   "C": {},
   "D": {},
   "E": {},
   "F": {},
}
VARIANTS = ["A", "B", "C", "D", "E", "F"]