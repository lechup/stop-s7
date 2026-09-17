"""Testy strony, danych mapy i ich zgodnosci z raportem.

Copyright (C) 2026 Leszek Piatek

Ten program jest wolnym oprogramowaniem: mozesz go rozpowszechniac i/lub
modyfikowac na warunkach Licencji AGPL GNU w wersji 3, opublikowanej przez
Free Software Foundation. Program rozpowszechniany jest w nadziei, ze bedzie
uzyteczny, ale BEZ JAKIEJKOLWIEK GWARANCJI. Szczegoly w pliku LICENSE.

Trzy grupy testow, kazda odpowiada na inne pytanie:

  statyczne   — czy strona w ogole zadziala (skladnia, kolizje nazw, brakujace
                elementy). Nie wymagaja danych ani przegladarki.
  dane        — czy mapa pokazuje te same liczby, co raport. Wymagaja
                docs/dane/ i raporty/podsumowanie.csv.
  przegladarka — czy filtry faktycznie filtruja. Wymagaja Chrome; wlaczane
                przelacznikiem --przegladarka, bo trwaja kilkanascie sekund.

Uruchomienie:
  .venv/bin/python testy.py                 # statyczne i danych
  .venv/bin/python testy.py --przegladarka  # komplet
"""

import csv
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

KATALOG = os.path.dirname(os.path.abspath(__file__))
STRONA = os.path.join(KATALOG, "docs", "index.html")
DANE = os.path.join(KATALOG, "docs", "dane")
PODSUMOWANIE = os.path.join(KATALOG, "raporty", "podsumowanie.csv")

# Znaczniki, ktore nie maja zamkniecia — reszta musi sie domykac.
PUSTE_ZNACZNIKI = {"meta", "link", "br", "img", "input", "hr", "source", "col"}


class Pominiete(Exception):
  """Testu nie da sie uruchomic w tym srodowisku (brak danych, brak Chrome)."""


# --------------------------------------------------------------------------
# pomocnicze

def tresc(sciezka):
  with open(sciezka, encoding="utf-8") as f:
    return f.read()


def skrypty(html):
  """Bloki <script> BEZ atrybutu src — czyli nasz wlasny kod."""
  return re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", html, re.S)


def wiersze_podsumowania():
  if not os.path.exists(PODSUMOWANIE):
    raise Pominiete("brak {} — policz raport".format(PODSUMOWANIE))
  with open(PODSUMOWANIE, encoding="utf-8") as f:
    return {w["wariant"]: w for w in csv.DictReader(f)}


def dane_json(nazwa):
  sciezka = os.path.join(DANE, nazwa)
  if not os.path.exists(sciezka):
    raise Pominiete("brak {} — uruchom eksport_web.py".format(sciezka))
  with open(sciezka, encoding="utf-8") as f:
    return json.load(f)


def warianty_z_danymi():
  nazwy = sorted(os.path.basename(p)[len("wariant-"):-len("-dzialki.geojson")]
                 for p in glob.glob(os.path.join(DANE, "wariant-*-dzialki.geojson")))
  if not nazwy:
    raise Pominiete("brak warstw dzialek — uruchom eksport_web.py")
  return nazwy


# --------------------------------------------------------------------------
# testy statyczne — nie wymagaja danych

def test_skladnia_skryptow():
  """Kazdy blok <script> musi byc poprawnym JavaScriptem."""
  if not shutil.which("node"):
    raise Pominiete("brak node — nie sprawdze skladni JS")
  for plik in glob.glob(os.path.join(KATALOG, "docs", "*.html")):
    for numer, blok in enumerate(skrypty(tresc(plik))):
      with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                       encoding="utf-8") as f:
        f.write(blok)
        tymczasowy = f.name
      try:
        wynik = subprocess.run(["node", "--check", tymczasowy],
                               capture_output=True, text=True)
      finally:
        os.unlink(tymczasowy)
      assert wynik.returncode == 0, "{} blok {}: {}".format(
          os.path.basename(plik), numer, wynik.stderr.strip().splitlines()[:3])


def test_nazwy_funkcji_sa_unikalne():
  """Dwie funkcje o tej samej nazwie = jedna po cichu zjada druga.

  Tak zepsul sie kiedys filtr budynkow: nowa funkcja zbudujListe() dla dzialek
  przykryla starsza o tej samej nazwie. Bez bledu w konsoli, bez objawow poza
  tym, ze filtr przestal filtrowac."""
  for plik in glob.glob(os.path.join(KATALOG, "docs", "*.html")):
    nazwy = []
    for blok in skrypty(tresc(plik)):
      nazwy += re.findall(r"^\s*function\s+([A-Za-z_$][\w$]*)", blok, re.M)
    powtorzone = sorted({n for n in nazwy if nazwy.count(n) > 1})
    assert not powtorzone, "{}: powtorzone nazwy funkcji {}".format(
        os.path.basename(plik), powtorzone)


def test_znaczniki_sie_domykaja():
  """Niedomkniety <div> potrafi wyrzucic pol panelu poza uklad."""
  from html.parser import HTMLParser

  class Kontrola(HTMLParser):
    def __init__(self):
      super().__init__()
      self.stos = []
      self.bledy = []

    def handle_starttag(self, znacznik, _atrybuty):
      if znacznik not in PUSTE_ZNACZNIKI:
        self.stos.append(znacznik)

    def handle_endtag(self, znacznik):
      if self.stos and self.stos[-1] == znacznik:
        self.stos.pop()
      elif znacznik in self.stos:
        self.bledy.append("</{}> zamyka takze {}".format(
            znacznik, self.stos[self.stos.index(znacznik) + 1:]))
        del self.stos[self.stos.index(znacznik):]

  for plik in glob.glob(os.path.join(KATALOG, "docs", "*.html")):
    kontrola = Kontrola()
    kontrola.feed(tresc(plik))
    nazwa = os.path.basename(plik)
    assert not kontrola.bledy, "{}: {}".format(nazwa, kontrola.bledy)
    assert not kontrola.stos, "{}: niedomkniete {}".format(nazwa, kontrola.stos)


def test_skrypt_nie_siega_po_nieistniejace_elementy():
  """getElementById("cos") ma sens tylko wtedy, gdy to "cos" jest w markupie.

  Literalne identyfikatory da sie sprawdzic statycznie — i to wlasnie one
  psuja sie przy przestawianiu paneli."""
  for plik in glob.glob(os.path.join(KATALOG, "docs", "*.html")):
    html = tresc(plik)
    obecne = set(re.findall(r'\sid="([^"]+)"', html))
    for blok in skrypty(html):
      # Identyfikatory sklejane z fragmentow ("podsumowanie-" + x) pomijamy,
      # bo statycznie nie da sie ich rozwinac.
      for identyfikator in re.findall(
          r'getElementById\(\s*"([^"]+)"\s*\)', blok):
        assert identyfikator in obecne, '{}: brak elementu o id "{}"'.format(
            os.path.basename(plik), identyfikator)


def test_warstwy_maja_przelaczniki():
  """Kazda warstwa z KOLEJNOSCI ma swoj przelacznik, i odwrotnie."""
  html = tresc(STRONA)
  # Z markupu, nie z kodu: w skryptach data-warstwa sklejane jest ze zmiennej
  # ('[data-warstwa="' + nazwa + '"]') i wpadloby tu jako smiec.
  bez_skryptow = re.sub(r"<script.*?</script>", "", html, flags=re.S)
  w_markupie = set(re.findall(r'data-warstwa="([^"]+)"', bez_skryptow))
  kolejnosc = re.search(r"const KOLEJNOSC = \{(.*?)\};", html, re.S)
  assert kolejnosc, "nie znalazlem definicji KOLEJNOSC"
  w_kodzie = set(re.findall(r"(\w+):\s*\d+", kolejnosc.group(1)))
  assert w_kodzie == w_markupie, (
      "warstwy w kodzie i w markupie sie roznia: tylko w kodzie {}, "
      "tylko w markupie {}".format(w_kodzie - w_markupie, w_markupie - w_kodzie))


# --------------------------------------------------------------------------
# testy danych — mapa kontra raport

def test_progi_zajecia_zgodne_z_raportem():
  """Kategorie na mapie musza dawac te same liczby, co kolumny raportu.

  Tu sie kiedys rozjechalo: mapa zaokraglala udzial do liczby calkowitej,
  wiec dzialka zajeta w 90,4% wypadala z kategorii "ponad 90%", a w CSV
  w niej zostawala."""
  raport = wiersze_podsumowania()
  for wariant in warianty_z_danymi():
    warstwa = dane_json("wariant-{}-dzialki.geojson".format(wariant))
    ponad90 = sum(1 for o in warstwa["features"] if o["properties"]["ud"] > 90)
    ponad50 = sum(1 for o in warstwa["features"] if o["properties"]["ud"] > 50)
    assert ponad90 == int(raport[wariant]["działki zajęte >90%"]), (
        "wariant {}: mapa {} dzialek >90%, raport {}".format(
            wariant, ponad90, raport[wariant]["działki zajęte >90%"]))
    assert ponad50 == int(raport[wariant]["działki zajęte >50%"]), (
        "wariant {}: mapa {} dzialek >50%, raport {}".format(
            wariant, ponad50, raport[wariant]["działki zajęte >50%"]))


def test_liczba_dzialek_w_warstwie():
  """Warstwa siega 200 m od drogi, tak jak adresy i budynki.

  Gdyby zawierala same dzialki przeciete przez droge, przelaczniki stref
  20/30/50/200 m nie mialyby czego pokazac i nie zmienialyby na mapie nic."""
  raport = wiersze_podsumowania()
  for wariant in warianty_z_danymi():
    warstwa = dane_json("wariant-{}-dzialki.geojson".format(wariant))
    assert len(warstwa["features"]) == int(raport[wariant]["działki ≤200 m"]), (
        "wariant {}: warstwa {} dzialek, raport {} w 200 m".format(
            wariant, len(warstwa["features"]), raport[wariant]["działki ≤200 m"]))


def test_strefy_dzialek_w_warstwie():
  """Kazda strefa ma na mapie tyle dzialek, ile mowi raport."""
  raport = wiersze_podsumowania()
  strefy = ["w śladzie", "nad tunelem", "w łącznicach",
            "0-20 m", "20-30 m", "30-50 m", "50-200 m"]
  for wariant in warianty_z_danymi():
    warstwa = dane_json("wariant-{}-dzialki.geojson".format(wariant))
    policzone = {}
    for obiekt in warstwa["features"]:
      strefa = obiekt["properties"]["strefa"]
      policzone[strefa] = policzone.get(strefa, 0) + 1
    assert set(policzone) <= set(strefy), "nieznana strefa: {}".format(
        set(policzone) - set(strefy))
    for strefa in strefy:
      kolumna = "działki {}".format(strefa)
      assert policzone.get(strefa, 0) == int(raport[wariant][kolumna]), (
          "wariant {}, strefa {}: mapa {}, raport {}".format(
              wariant, strefa, policzone.get(strefa, 0), raport[wariant][kolumna]))


def test_dzialki_maja_komplet_opisu():
  """Popup ma z czego zbudowac odpowiedz: identyfikator, obreb, strefa, odleglosc.

  Do tego udzial zajecia i odleglosc musza sie zgadzac: dzialka zajeta lezy
  w zerowej odleglosci, a ta poza zajeciem ma udzial rowny zeru."""
  przy_drodze = {"w śladzie", "nad tunelem", "w łącznicach"}
  for wariant in warianty_z_danymi():
    warstwa = dane_json("wariant-{}-dzialki.geojson".format(wariant))
    for obiekt in warstwa["features"]:
      p = obiekt["properties"]
      for pole in ("teryt", "obreb", "nr", "strefa", "odl", "ud"):
        assert pole in p, "brak pola {} w dzialce {}".format(pole, p.get("teryt"))
      assert p["teryt"], "dzialka bez identyfikatora TERYT"
      if p["strefa"] in przy_drodze:
        assert p["odl"] == 0, "{}: strefa {}, a odleglosc {}".format(
            p["teryt"], p["strefa"], p["odl"])
        # Udzialu NIE wymagamy dodatniego: dzialka moze musnac slad rogiem
        # i miec zajecie ponizej 0,05%, ktore zaokragla sie do zera. Raport
        # liczy ja tak samo (przecina = zajeta), wiec to nie jest niespojnosc.
        assert p["ud"] >= 0, "{}: ujemny udzial zajecia".format(p["teryt"])
      else:
        assert p["ud"] == 0, "{}: strefa {}, a udzial zajecia {}".format(
            p["teryt"], p["strefa"], p["ud"])
        # Odleglosc musi pasowac do nazwy strefy. Granice bierzemy domkniete
        # z obu stron, bo odleglosc idzie zaokraglona do decymetra — dzialka
        # 4 cm od drogi ma w danych 0,0 m, a nadal nalezy do strefy 0-20 m.
        od, do = (int(x) for x in p["strefa"].split(" ")[0].split("-"))
        assert od <= p["odl"] <= do, "{}: strefa {}, a odleglosc {} m".format(
            p["teryt"], p["strefa"], p["odl"])


def test_dzialki_zabudowane_zgodne_z_raportem():
  raport = wiersze_podsumowania()
  for wariant in warianty_z_danymi():
    warstwa = dane_json("wariant-{}-dzialki.geojson".format(wariant))
    przy_drodze = {"w śladzie", "nad tunelem", "w łącznicach"}
    zabudowane = sum(1 for o in warstwa["features"]
                     if o["properties"]["zab"]
                     and o["properties"]["strefa"] in przy_drodze)
    assert zabudowane == int(raport[wariant]["działki zabudowane"]), (
        "wariant {}: mapa {} zabudowanych, raport {}".format(
            wariant, zabudowane, raport[wariant]["działki zabudowane"]))


def test_strefy_dzialek_w_miarach():
  """Panel miar bierze strefy dzialek z raportu — musza sie zgadzac i sumowac."""
  miary = dane_json("miary.json")
  raport = wiersze_podsumowania()
  assert miary.get("dzialki_w_strefach"), "miary.json bez stref dzialek"
  for wariant, strefy in miary["dzialki_w_strefach"].items():
    przy_drodze = sum(strefy.get(s, 0)
                      for s in ("w śladzie", "nad tunelem", "w łącznicach"))
    assert przy_drodze == int(raport[wariant]["działki"]), (
        "wariant {}: strefy przy drodze sumuja sie do {}, a raport ma {}".format(
            wariant, przy_drodze, raport[wariant]["działki"]))
    razem = sum(strefy.values())
    assert razem == int(raport[wariant]["działki ≤200 m"]), (
        "wariant {}: strefy sumuja sie do {}, a raport ma {} w 200 m".format(
            wariant, razem, raport[wariant]["działki ≤200 m"]))


def test_indeks_adresow_zgodny_z_raportem():
  """Kody stref w indeksie wyszukiwarki kontra kolumny podsumowania."""
  indeks = dane_json("adresy-index.json")
  raport = wiersze_podsumowania()
  kody = {"w śladzie": 1, "nad tunelem": 2, "w łącznicach": 3}
  for numer, wariant in enumerate(indeks["warianty"]):
    for nazwa, kod in kody.items():
      w_indeksie = sum(1 for w in indeks["adresy"] if w[6][numer][1] == kod)
      assert w_indeksie == int(raport[wariant][nazwa]), (
          "wariant {}: indeks ma {} adresow '{}', raport {}".format(
              wariant, w_indeksie, nazwa, raport[wariant][nazwa]))


def test_json_bez_nan():
  """NaN jest legalny w Pythonie, ale JSON.parse go odrzuca — cala mapa pada."""
  for sciezka in glob.glob(os.path.join(DANE, "*.json")) + \
                 glob.glob(os.path.join(DANE, "*.geojson")):
    surowy = tresc(sciezka)
    for zakazane in ("NaN", "Infinity"):
      assert zakazane not in surowy, "{} zawiera {}".format(
          os.path.basename(sciezka), zakazane)


def test_indeks_dzialek_ma_spojne_wpisy():
  """Wiersz indeksu: teryt, obreb, nr, gmina, powierzchnia, lon, lat, wartosci, km."""
  indeks = dane_json("dzialki-index.json")
  assert indeks["dzialki"], "pusty indeks dzialek"
  warianty = set(indeks["warianty"])
  for wiersz in indeks["dzialki"][:2000]:
    assert len(wiersz) == 9, "zly rozmiar wiersza: {}".format(len(wiersz))
    assert set(wiersz[7]) <= warianty, "nieznany wariant w {}".format(wiersz[0])
    assert 14 < wiersz[5] < 25 and 48 < wiersz[6] < 55, (
        "wspolrzedne poza Polska: {}".format(wiersz[:7]))


# --------------------------------------------------------------------------
# testy w przegladarce

class _CichyHandler(http.server.SimpleHTTPRequestHandler):
  """Bez logu na stderr — inaczej kazde zadanie o kafelek zasmieca wynik testow."""

  def log_message(self, *_args):
    pass


def _serwuj(katalog):
  """Maly serwer HTTP na losowym porcie; zwraca (adres, funkcja zatrzymujaca)."""

  def utworz(*args, **kwargs):
    return _CichyHandler(*args, directory=katalog, **kwargs)

  serwer = http.server.ThreadingHTTPServer(("127.0.0.1", 0), utworz)
  threading.Thread(target=serwer.serve_forever, daemon=True).start()
  return "http://127.0.0.1:{}".format(serwer.server_port), serwer.shutdown


def _w_przegladarce(skrypt_testu, sekundy=30):
  """Uruchamia skrypt w kontekscie strony i zwraca to, co wpisze w document.title.

  Strona i harness leza w tym samym katalogu, wiec ramka jest same-origin
  i da sie ja wysterowac — inaczej przegladarka zablokuje dostep."""
  if not os.path.isdir(DANE):
    raise Pominiete("brak docs/dane — uruchom eksport_web.py")
  chrome = next((s for s in ("google-chrome", "google-chrome-stable", "chromium")
                 if shutil.which(s)), None)
  if not chrome:
    raise Pominiete("brak Chrome — pomijam testy w przegladarce")

  harness = os.path.join(KATALOG, "docs", "_harness.html")
  with open(harness, "w", encoding="utf-8") as f:
    f.write("""<!doctype html><meta charset="utf-8"><title>czekam</title>
<iframe id="ramka" src="index.html#A/12/49.95/19.93"
        style="width:1200px;height:860px;border:0"></iframe>
<script>
const okno = () => document.getElementById("ramka").contentWindow;
const dok = () => okno().document;
const zglos = (wynik) => { document.title = JSON.stringify(wynik); };
%s
</script>""" % skrypt_testu)

  adres, zatrzymaj = _serwuj(os.path.join(KATALOG, "docs"))
  try:
    wynik = subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
         "--window-size=1300,900",
         "--virtual-time-budget={}".format(sekundy * 1000),
         "--dump-dom", adres + "/_harness.html"],
        capture_output=True, text=True, timeout=sekundy * 3)
  finally:
    zatrzymaj()
    os.unlink(harness)

  tytul = re.search(r"<title>(.*?)</title>", wynik.stdout, re.S)
  assert tytul, "strona nie odpowiedziala"
  assert tytul.group(1) != "czekam", "test nie zdazyl sie wykonac"
  return json.loads(tytul.group(1).replace("&quot;", '"').replace("&amp;", "&"))


def test_przegladarka_filtr_budynkow():
  """Zawezenie rodzaju budynkow musi zmieniac to, co widac i co pokazuja liczby."""
  wynik = _w_przegladarce("""
setTimeout(() => {
  const przed = dok().getElementById("razem-budynki").textContent;
  dok().querySelectorAll("#lista-rodzajow input").forEach((p, i) => {
    if (i > 0 && p.checked) p.click();
  });
  setTimeout(() => zglos({
    przed: przed,
    po: dok().getElementById("razem-budynki").textContent,
    pozycji: dok().querySelectorAll("#lista-rodzajow label").length,
    opis: dok().getElementById("podsumowanie-rodzajow").textContent,
  }), 1500);
}, 5000);""")
  liczba = lambda tekst: int(re.sub(r"[^\d]", "", tekst) or 0)
  assert wynik["pozycji"] > 1, "lista rodzajow budynkow jest pusta"
  assert liczba(wynik["po"]) > 0, "po zawezeniu nie zostal zaden budynek"
  assert liczba(wynik["po"]) < liczba(wynik["przed"]), (
      "zawezenie rodzaju nie zmienilo liczby budynkow ({} -> {})".format(
          wynik["przed"], wynik["po"]))


def test_przegladarka_filtr_dzialek():
  """Filtr udzialu zajecia musi dawac liczby zgodne z raportem."""
  raport = wiersze_podsumowania()
  wynik = _w_przegladarce("""
setTimeout(() => { dok().querySelector('[data-warstwa="dzialki"]').click(); }, 3000);
setTimeout(() => {
  const wszystkie = dok().getElementById("licznik-dzialek").textContent;
  dok().querySelector('[data-zajecie="0"]').click();
  dok().querySelector('[data-zajecie="50"]').click();
  setTimeout(() => {
    const ponad90 = dok().getElementById("licznik-dzialek").textContent;
    dok().querySelector('[data-zabudowa="0"]').click();
    setTimeout(() => zglos({
      wszystkie: wszystkie,
      ponad90: ponad90,
      ponad90zabudowane: dok().getElementById("licznik-dzialek").textContent,
    }), 1200);
  }, 1200);
}, 8000);""", sekundy=40)
  liczba = lambda tekst: int(re.sub(r"[^\d]", "", tekst) or 0)
  assert liczba(wynik["wszystkie"]) == int(raport["A"]["działki ≤200 m"]), (
      "mapa pokazuje {} dzialek, raport {} w 200 m".format(
          wynik["wszystkie"], raport["A"]["działki ≤200 m"]))
  assert liczba(wynik["ponad90"]) == int(raport["A"]["działki zajęte >90%"]), (
      "po zawezeniu do >90% mapa ma {}, raport {}".format(
          wynik["ponad90"], raport["A"]["działki zajęte >90%"]))
  assert 0 < liczba(wynik["ponad90zabudowane"]) < liczba(wynik["ponad90"]), (
      "dolozenie filtra zabudowy nic nie zmienilo")


def test_przegladarka_strefy_dzialek():
  """Odklikanie strefy musi zmieniac liczbe dzialek na mapie.

  Tak sie kiedys nie dzialo: warstwa miala wylacznie dzialki przeciete przez
  droge, wiec strefy 20/30/50/200 m nie mialy czego pokazac, a odklikanie
  "w śladzie" nie zmienialo niczego widocznego."""
  raport = wiersze_podsumowania()
  wynik = _w_przegladarce("""
setTimeout(() => { dok().querySelector('[data-warstwa="dzialki"]').click(); }, 3000);
setTimeout(() => {
  const wszystkie = dok().getElementById("licznik-dzialek").textContent;
  dok().querySelector('[data-strefa="50-200 m"]').click();
  setTimeout(() => {
    const bez50_200 = dok().getElementById("licznik-dzialek").textContent;
    dok().querySelectorAll("[data-strefa]").forEach((p, i) => {
      if (i > 0 && p.checked) p.click();
    });
    setTimeout(() => zglos({
      wszystkie: wszystkie,
      bez50_200: bez50_200,
      samSlad: dok().getElementById("licznik-dzialek").textContent,
      wStrefieTabela: dok().querySelector('[data-wiersz="50-200 m"] [data-liczba="dzialki"]').textContent,
    }), 1200);
  }, 1200);
}, 9000);""", sekundy=45)
  liczba = lambda tekst: int(re.sub(r"[^\d]", "", tekst) or 0)
  assert liczba(wynik["wszystkie"]) == int(raport["A"]["działki ≤200 m"]), (
      "mapa pokazuje {} dzialek, raport {} w 200 m".format(
          wynik["wszystkie"], raport["A"]["działki ≤200 m"]))
  assert liczba(wynik["bez50_200"]) == (
      int(raport["A"]["działki ≤200 m"]) - int(raport["A"]["działki 50-200 m"])), (
      "po odkliknieciu strefy 50-200 m zostalo {}".format(wynik["bez50_200"]))
  assert liczba(wynik["samSlad"]) == int(raport["A"]["działki w śladzie"]), (
      "przy samej strefie 'w śladzie' mapa ma {}, raport {}".format(
          wynik["samSlad"], raport["A"]["działki w śladzie"]))


def test_przegladarka_opis_dzialki():
  """Popup dzialki musi podawac identyfikator, obreb i los dzialki."""
  wynik = _w_przegladarce("""
setTimeout(() => zglos({
  zajeta: okno().opisObiektu({ warstwa: "dzialki", teryt: "120903_4.0002.370",
    obreb: "Myślenice 2", nr: "370", gmina: "Myślenice", pow: 9183, zab: 1,
    strefa: "w śladzie", odl: 0, ud: 7.4 }),
  daleka: okno().opisObiektu({ warstwa: "dzialki", teryt: "120903_4.0002.371",
    obreb: "Myślenice 2", nr: "371", gmina: "Myślenice", pow: 500, zab: 0,
    strefa: "30-50 m", odl: 42.3, ud: 0 }),
}), 5000);""")
  for czego_szukam in ("120903_4.0002.370", "Myślenice 2", "dz. 370",
                       "zajęta w 7,4%", "zabudowana"):
    assert czego_szukam in wynik["zajeta"], (
        "w opisie zajętej brakuje {} — opis brzmi: {}".format(
            czego_szukam, wynik["zajeta"]))
  assert "42 m od drogi" in wynik["daleka"], (
      "opis dalekiej dzialki nie podaje odleglosci: {}".format(wynik["daleka"]))
  assert "30-50 m" in wynik["daleka"], "opis dalekiej dzialki nie podaje strefy"


def test_przegladarka_tabela_stref():
  """Stopka tabeli stref musi sumowac sie do kolumn ≤200 m z raportu."""
  raport = wiersze_podsumowania()
  wynik = _w_przegladarce("""
setTimeout(() => zglos({
  adresy: dok().getElementById("razem-adresy").textContent,
  budynki: dok().getElementById("razem-budynki").textContent,
  dzialki: dok().getElementById("razem-dzialki").textContent,
  wierszy: dok().querySelectorAll(".strefy-tab tbody tr").length,
}), 6000);""")
  liczba = lambda tekst: int(re.sub(r"[^\d]", "", tekst) or 0)
  assert wynik["wierszy"] == 7, "tabela stref ma {} wierszy zamiast 7".format(
      wynik["wierszy"])
  assert liczba(wynik["adresy"]) == int(raport["A"]["≤200 m"]), (
      "adresy: mapa {}, raport {}".format(wynik["adresy"], raport["A"]["≤200 m"]))
  assert liczba(wynik["dzialki"]) == int(raport["A"]["działki ≤200 m"]), (
      "dzialki: mapa {}, raport {}".format(
          wynik["dzialki"], raport["A"]["działki ≤200 m"]))


# --------------------------------------------------------------------------

def main():
  z_przegladarka = "--przegladarka" in sys.argv
  testy = [(nazwa, funkcja) for nazwa, funkcja in sorted(globals().items())
           if nazwa.startswith("test_") and callable(funkcja)]
  if not z_przegladarka:
    testy = [(n, f) for n, f in testy if not n.startswith("test_przegladarka")]

  bledy, pominiete = [], []
  for nazwa, funkcja in testy:
    etykieta = nazwa[len("test_"):].replace("_", " ")
    try:
      funkcja()
      print("  OK       {}".format(etykieta))
    except Pominiete as powod:
      pominiete.append(nazwa)
      print("  pomijam  {} ({})".format(etykieta, powod))
    except AssertionError as blad:
      bledy.append(nazwa)
      print("  BŁĄD     {}\n             {}".format(etykieta, blad))

  print("\n{} przeszło, {} nie przeszło, {} pominięto".format(
      len(testy) - len(bledy) - len(pominiete), len(bledy), len(pominiete)))
  if not z_przegladarka:
    print("Testy w przeglądarce: .venv/bin/python testy.py --przegladarka")
  return 1 if bledy else 0


if __name__ == "__main__":
  sys.exit(main())
