"""Pobiera dane wejściowe (warianty GML, adresy PRG) z release'a na GitHubie.

Dane nie są trzymane w repozytorium, bo po rozpakowaniu zajmują ok. 1,3 GB.
Zwykłe uruchomienie pobiera brakujące paczki i rozpakowuje je w katalogu projektu:

    python3 pobierz_dane.py

Korzysta wyłącznie z biblioteki standardowej, więc działa przed instalacją
zależności z requirements.txt.
"""

import argparse
import hashlib
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

import dane

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "dane-archiwa"
CHUNK = 1024 * 1024


def human(size):
  for unit in ("B", "KB", "MB", "GB"):
    if size < 1024 or unit == "GB":
      return "{:.1f} {}".format(size, unit)
    size /= 1024


def sha256(path):
  h = hashlib.sha256()
  with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(CHUNK), b""):
      h.update(chunk)
  return h.hexdigest()


def progress(done, total):
  if total:
    pct = done * 100 / total
    bar = "#" * int(pct / 2.5)
    line = "  [{:<40}] {:5.1f}%  {}".format(bar, pct, human(done))
  else:
    line = "  pobrano {}".format(human(done))
  sys.stdout.write("\r" + line)
  sys.stdout.flush()


def download(url, target):
  """Pobiera url do target (przez plik .part, żeby przerwanie nie zostawiło śmiecia)."""
  part = target.with_suffix(target.suffix + ".part")
  try:
    with urllib.request.urlopen(url) as response:
      total = int(response.headers.get("Content-Length") or 0)
      done = 0
      with open(part, "wb") as f:
        while True:
          chunk = response.read(CHUNK)
          if not chunk:
            break
          f.write(chunk)
          done += len(chunk)
          progress(done, total)
    sys.stdout.write("\n")
  except urllib.error.HTTPError as exc:
    part.unlink(missing_ok=True)
    if exc.code == 404:
      raise SystemExit(
          "\nBłąd 404: nie ma takiego pliku.\n"
          "Sprawdź, czy release '{}' istnieje w repozytorium {} i czy repozytorium\n"
          "jest publiczne (dla prywatnego pobieranie wymaga tokena).\n"
          "Adres: {}".format(dane.DATA_TAG, dane.REPO, url)
      )
    raise SystemExit("\nBłąd HTTP {} przy pobieraniu {}".format(exc.code, url))
  except urllib.error.URLError as exc:
    part.unlink(missing_ok=True)
    raise SystemExit("\nBrak połączenia z GitHubem: {}".format(exc.reason))

  part.replace(target)


def verify(path, expected):
  if not expected:
    print("  (pomijam weryfikację — brak sumy kontrolnej w dane.py)")
    return
  print("  sprawdzam sumę kontrolną...")
  actual = sha256(path)
  if actual != expected:
    path.unlink(missing_ok=True)
    raise SystemExit(
        "  Suma kontrolna się nie zgadza!\n"
        "    oczekiwano: {}\n"
        "    otrzymano:  {}\n"
        "  Plik został usunięty. Uruchom skrypt ponownie; jeśli błąd wraca,\n"
        "  zaktualizuj sumy w dane.py (pobierz_dane.py --sumy).".format(expected, actual)
    )


def extract(archive, target_dir):
  print("  rozpakowuję do {}/ ...".format(target_dir.name))
  with tarfile.open(archive, "r:gz") as tar:
    # filter="data" blokuje wyjście poza katalog docelowy (ścieżki bezwzględne, ../)
    tar.extractall(ROOT, filter="data")


def pobierz(force=False, keep=False):
  CACHE_DIR.mkdir(exist_ok=True)

  for name, (dirname, expected) in dane.ARCHIVES.items():
    target_dir = ROOT / dirname
    print("\n{}:".format(name))

    if target_dir.is_dir() and any(target_dir.iterdir()) and not force:
      print("  {}/ już istnieje — pomijam (--force pobiera od nowa)".format(dirname))
      continue

    archive = CACHE_DIR / name
    if archive.exists() and expected and sha256(archive) == expected:
      print("  archiwum już pobrane ({})".format(human(archive.stat().st_size)))
    else:
      url = dane.DOWNLOAD_URL.format(repo=dane.REPO, tag=dane.DATA_TAG, name=name)
      print("  pobieram {}".format(url))
      download(url, archive)
      verify(archive, expected)

    if force and target_dir.is_dir():
      shutil.rmtree(target_dir)
    extract(archive, target_dir)

    if not keep:
      archive.unlink(missing_ok=True)

  print("\nGotowe. Możesz uruchomić: python3 raport.py")


def sumy():
  """Wypisuje ARCHIVES z aktualnymi sumami — do wklejenia w dane.py po nowym release."""
  if not CACHE_DIR.is_dir():
    raise SystemExit("Brak katalogu {}/ z archiwami.".format(CACHE_DIR.name))

  print("ARCHIVES = {")
  for name, (dirname, _) in dane.ARCHIVES.items():
    path = CACHE_DIR / name
    if not path.exists():
      print('    # brak pliku {} — pomijam'.format(name))
      continue
    print('    "{}": ("{}", "{}"),'.format(name, dirname, sha256(path)))
  print("}")


parser = argparse.ArgumentParser(
    description="Pobiera dane wejściowe do analizy wariantów S7."
)
parser.add_argument(
    "--force",
    action="store_true",
    help="Pobierz i rozpakuj od nowa, nawet jeśli katalogi z danymi już istnieją"
)
parser.add_argument(
    "--keep",
    action="store_true",
    help="Zostaw pobrane archiwa w dane-archiwa/ zamiast kasować je po rozpakowaniu"
)
parser.add_argument(
    "--sumy",
    action="store_true",
    help="Policz sumy sha256 archiwów w dane-archiwa/ i wypisz gotowy wpis do dane.py"
)

if __name__ == "__main__":
  args = parser.parse_args()
  if args.sumy:
    sumy()
  else:
    pobierz(force=args.force, keep=args.keep)
