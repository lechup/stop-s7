#!/usr/bin/env bash
# Uruchamia raport w cgroupie z twardym limitem pamieci.
#
# Powod: budowanie sladu drogi to operacje na geometrii o setkach tysiecy
# wierzcholkow. Puszczone bez limitu potrafia zjesc kilkanascie GB, a wtedy
# systemd-oomd ubija cala sesje uzytkownika (gnome-shell, dbus, edytor) —
# nie sam skrypt. Z limitem ginie wylacznie ten proces.
#
# Uzycie:  ./uruchom.sh [argumenty raport.py]
#   ./uruchom.sh --wariant A --metoda dokladna
#   LIMIT=8G ./uruchom.sh --mode debug

set -euo pipefail
cd "$(dirname "$0")"

LIMIT="${LIMIT:-6G}"

if [ ! -x .venv/bin/python ]; then
  echo "Brak .venv w projekcie. Utworz go:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -d warianty ] || [ ! -d wojewodztwa-adresy ]; then
  echo "Brak danych wejsciowych. Pobierz je:" >&2
  echo "  python3 pobierz_dane.py" >&2
  exit 1
fi

if command -v systemd-run >/dev/null && [ -d "/run/user/$(id -u)" ]; then
  exec env "XDG_RUNTIME_DIR=/run/user/$(id -u)" systemd-run --user --scope -q \
    -p "MemoryMax=$LIMIT" -p MemorySwapMax=256M \
    -- .venv/bin/python -u raport.py "$@"
else
  # Bez systemd (np. w kontenerze) — ograniczenie przez ulimit na pamiec wirtualna.
  echo "systemd-run niedostepny, ograniczam przez ulimit -v" >&2
  ( ulimit -v $(( ${LIMIT%G} * 1024 * 1024 )); exec .venv/bin/python -u raport.py "$@" )
fi
