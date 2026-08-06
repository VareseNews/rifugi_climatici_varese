"""
Aggiorna i dati della mappa dei rifugi climatici.

Gira su GitHub ogni ora. Legge il foglio pubblico delle segnalazioni, geolocalizza
gli indirizzi nuovi e riscrive dati/rifugi.json. Non tocca nessun account Google:
usa solo il link pubblico del foglio, quello che puo' aprire chiunque.

Gli indirizzi gia' risolti restano in dati/cache-geocoding.json e non vengono
richiesti una seconda volta: a regime le chiamate al geocoder sono zero.
"""

import csv, io, json, os, sys, time, unicodedata, urllib.parse, urllib.request

# --------------------------------------------------------------------------
# Impostazioni
# --------------------------------------------------------------------------
FOGLIO = ("https://docs.google.com/spreadsheets/d/"
          "1sIA5jmN86gPWXrlQ3AX2FwT6oyj1EnMvj5ymNR64Z78/export?format=csv&gid=0")

BBOX = dict(sud=45.50, ovest=8.48, nord=46.18, est=9.13)   # provincia di Varese
UA = "RifugiClimaticiVarese/1.0 (VareseNews; mappa dei rifugi climatici)"
PAUSA = 1.1          # policy Nominatim: al massimo una richiesta al secondo
MAX_NUOVI = 40       # tetto per esecuzione, per non fare raffiche di richieste
TIMEOUT = 12         # secondi per singola richiesta
BUDGET = 240         # oltre 4 minuti si smette: il resto al giro dopo

AVVIO = time.time()
BLOCCATO = {"nominatim": False}   # se il geocoder ci sbatte la porta, non insistiamo

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USCITA = os.path.join(QUI, "dati", "rifugi.json")
CACHE = os.path.join(QUI, "dati", "cache-geocoding.json")
COMUNI = os.path.join(QUI, "dati", "comuni-varese.geojson")

# --------------------------------------------------------------------------
# Riconoscimento delle colonne: il foglio arriva da un Google Form, quindi le
# intestazioni sono le domande per esteso e possono cambiare formulazione.
# --------------------------------------------------------------------------
ALIAS = [
    ("lat",        ["lat", "latitudine", "latitude"]),
    ("lon",        ["lon", "lng", "long", "longitudine", "longitude"]),
    ("pubblica",   ["pubblica", "pubblicare", "pubblicato", "validato", "valida",
                    "approvato", "online"]),
    ("comune",     ["comune", "citta", "paese", "comunedelluogo"]),
    ("tipologia",  ["tipologia", "tipo", "categoria", "tipodiluogo",
                    "naturaleoclimatizzato", "naturale", "climatizzato"]),
    ("indirizzo",  ["indirizzo", "via", "viaenumerocivico", "indirizzocompleto",
                    "viaecivico", "numerocivico"]),
    ("orari",      ["orari", "orario", "oraridiapertura", "apertura"]),
    ("accesso",    ["accesso", "accessolibero", "gratuito", "ingresso",
                    "gratisoapagamento", "gratis", "pagamento", "costo"]),
    ("natura",     ["pubblicooprivato", "pubblicoprivato", "pubblico", "privato", "gestione"]),
    ("servizi",    ["servizi", "cosaoffre", "dotazioni", "caratteristiche"]),
    ("maps",       ["linkgooglemaps", "googlemaps", "linkmaps", "link", "url"]),
    ("note",       ["note", "descrizione", "noteaggiuntive", "commenti"]),
    ("nome",       ["nome", "nomedelluogo", "luogo", "denominazione", "struttura", "titolo"]),
]

VERO = {"si", "s", "sì", "yes", "y", "x", "true", "vero", "ok", "1"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c for c in s if c.isalnum())


def individua_colonne(intestazioni):
    normalizzate = [norm(h) for h in intestazioni]
    presi, col = set(), {}
    for passata in (0, 1):
        for campo, alias in ALIAS:
            if campo in col:
                continue
            for i, h in enumerate(normalizzate):
                if i in presi or not h:
                    continue
                trovato = (h in alias) if passata == 0 else any(
                    len(a) >= 3 and (a in h or h in a) for a in alias)
                if trovato:
                    col[campo] = i
                    presi.add(i)
                    break
    return col


# --------------------------------------------------------------------------
# Pulizia dei valori scritti dai lettori
# --------------------------------------------------------------------------
def etichetta(v):
    """Prima lettera maiuscola, il resto com'e': non storpia 'villa Mylius'."""
    v = str(v or "").strip()
    return v[0].upper() + v[1:] if v else ""


def costo(v):
    n = norm(v)
    if not n:
        return ""
    if "pagament" in n:
        return "A pagamento"
    if "gratis" in n or "gratuit" in n:
        return "Gratis"
    return etichetta(v)


def carica_nomi_comuni():
    """Nome normalizzato -> nome ISTAT ufficiale. Serve ad accendere il confine."""
    with io.open(COMUNI, encoding="utf-8") as f:
        g = json.load(f)
    return {norm(x["properties"]["nome"]): x["properties"]["nome"] for x in g["features"]}


def dentro_provincia(lat, lon):
    return (BBOX["sud"] <= lat <= BBOX["nord"]) and (BBOX["ovest"] <= lon <= BBOX["est"])


# --------------------------------------------------------------------------
# Geocodifica
# --------------------------------------------------------------------------
def scaduto():
    return time.time() - AVVIO > BUDGET


def interroga(parametri):
    """Nominatim, con Photon come rete di sicurezza.

    Nominatim rifiuta spesso le richieste che partono dai server di GitHub.
    Se succede smettiamo subito di interpellarlo per questa esecuzione, invece
    di aspettare un timeout dopo l'altro, e passiamo a Photon (sempre dati
    OpenStreetMap, nessuna chiave, politica d'uso piu' permissiva)."""
    if not BLOCCATO["nominatim"]:
        p = {"format": "jsonv2", "limit": 5, "countrycodes": "it", "bounded": 1,
             "viewbox": f"{BBOX['ovest']},{BBOX['nord']},{BBOX['est']},{BBOX['sud']}"}
        p.update(parametri)
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                risultati = json.load(r)
            punto = primo_dentro(risultati, "lat", "lon")
            if punto:
                return punto
        except urllib.error.HTTPError as e:
            print(f"    ! Nominatim risponde {e.code}: passo a Photon")
            BLOCCATO["nominatim"] = True
        except Exception as e:
            print(f"    ! Nominatim non raggiungibile ({e}): passo a Photon")
            BLOCCATO["nominatim"] = True
        finally:
            time.sleep(PAUSA)

    return interroga_photon(parametri)


def interroga_photon(parametri):
    testo = parametri.get("q") or ", ".join(
        v for v in (parametri.get("street"), parametri.get("city")) if v)
    if not testo:
        return None
    # niente parametro "lang": Photon accetta solo alcune lingue e con "it"
    # risponde 400. lat/lon servono solo a preferire i risultati vicini.
    p = {"q": testo + ", Italia", "limit": 5,
         "lat": (BBOX["sud"] + BBOX["nord"]) / 2,
         "lon": (BBOX["ovest"] + BBOX["est"]) / 2}
    url = "https://photon.komoot.io/api?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            dati = json.load(r)
    except Exception as e:
        print(f"    ! anche Photon non risponde: {e}")
        return None
    finally:
        time.sleep(0.6)

    for f in dati.get("features", []):
        lon, lat = f["geometry"]["coordinates"]
        if dentro_provincia(lat, lon):
            return {"lat": round(lat, 6), "lon": round(lon, 6)}
    return None


def primo_dentro(risultati, chiave_lat, chiave_lon):
    for d in risultati:
        lat, lon = float(d[chiave_lat]), float(d[chiave_lon])
        if dentro_provincia(lat, lon):
            return {"lat": round(lat, 6), "lon": round(lon, 6)}
    return None


def coordinate_da_link(link):
    """Se il lettore ha incollato un link di Google Maps le coordinate sono li' dentro."""
    import re
    if re.match(r"^https?://(maps\.app\.goo\.gl|goo\.gl/maps)", link, re.I):
        try:
            req = urllib.request.Request(link, headers={"User-Agent": UA})
            classe = urllib.request.HTTPRedirectHandler
            opener = urllib.request.build_opener(classe)
            with opener.open(req, timeout=20) as r:
                link = r.geturl()
        except Exception:
            return None
    for schema in (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
                   r"[?&]q=(-?\d+\.\d+),\s*(-?\d+\.\d+)",
                   r"@(-?\d+\.\d+),(-?\d+\.\d+)"):
        m = re.search(schema, link)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if dentro_provincia(lat, lon):
                return {"lat": round(lat, 6), "lon": round(lon, 6)}
    return None


def geocodifica(nome, indirizzo, comune):
    """Tre tentativi, dal piu' preciso al piu' generico."""
    if indirizzo and comune:
        p = interroga({"street": indirizzo, "city": comune})
        if p:
            return p, "indirizzo"
    if nome and comune:
        p = interroga({"q": f"{nome}, {comune}, Italia"})
        if p:
            return p, "nome del luogo"
    if indirizzo and comune:
        via = indirizzo.split(",")[0].rstrip("0123456789 ")
        if via:
            p = interroga({"street": via, "city": comune})
            if p:
                return p, "via senza civico"
    return None, None


# --------------------------------------------------------------------------
def main():
    print("Scarico il foglio…")
    req = urllib.request.Request(FOGLIO, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        testo = r.read().decode("utf-8")
    if testo.lstrip().startswith("<"):
        sys.exit("Il foglio non e' leggibile: controlla che sia condiviso "
                 "come 'Chiunque abbia il link: visualizzatore'.")

    righe = list(csv.reader(io.StringIO(testo)))
    righe = [r for r in righe if any(c.strip() for c in r)]
    if len(righe) < 2:
        sys.exit("Il foglio non contiene segnalazioni.")

    col = individua_colonne(righe[0])
    print("Colonne riconosciute:", {k: righe[0][v] for k, v in sorted(col.items())})

    nomi_comuni = carica_nomi_comuni()
    cache = {}
    if os.path.exists(CACHE):
        with io.open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)

    def val(r, campo):
        i = col.get(campo)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    rifugi, in_attesa, nuovi = [], 0, 0

    for r in righe[1:]:
        # filtro redazionale: se la colonna non c'e', si pubblica tutto
        if "pubblica" in col and norm(val(r, "pubblica")) not in VERO:
            continue

        nome = etichetta(val(r, "nome"))
        grezzo = val(r, "comune")
        comune = nomi_comuni.get(norm(grezzo), grezzo.strip())
        indirizzo = val(r, "indirizzo")
        if not nome and not comune:
            continue

        punto, origine = None, ""

        # 1) coordinate messe a mano nel foglio: hanno sempre la precedenza
        try:
            lat = float(val(r, "lat").replace(",", "."))
            lon = float(val(r, "lon").replace(",", "."))
            if dentro_provincia(lat, lon):
                punto, origine = {"lat": lat, "lon": lon}, "corretta a mano"
        except ValueError:
            pass

        # 2) gia' geocodificata in passato
        chiave = f"{norm(indirizzo)}|{norm(comune)}|{norm(nome)}"
        if not punto and chiave in cache:
            punto, origine = cache[chiave], cache[chiave].get("origine", "cache")

        # 3) link di Google Maps incollato dal lettore
        if not punto and val(r, "maps"):
            p = coordinate_da_link(val(r, "maps"))
            if p:
                punto, origine = p, "link Google Maps"

        # 4) geocodifica vera e propria, solo per gli indirizzi mai visti
        if not punto:
            if nuovi >= MAX_NUOVI or scaduto():
                in_attesa += 1
                continue
            nuovi += 1
            print(f"  geocodifico: {nome} — {indirizzo}, {comune}")
            p, origine = geocodifica(nome, indirizzo, comune)
            if p:
                punto = p
                cache[chiave] = {**p, "origine": origine}
            else:
                print("    non trovato")
                in_attesa += 1
                continue

        rifugi.append({
            "nome": nome or "Senza nome",
            "comune": comune,
            "indirizzo": indirizzo,
            "tipologia": etichetta(val(r, "tipologia")),
            "orari": val(r, "orari"),
            "accesso": costo(val(r, "accesso")),
            "natura": etichetta(val(r, "natura")),
            "servizi": val(r, "servizi"),
            "note": val(r, "note"),
            "lat": punto["lat"],
            "lon": punto["lon"],
            "precisione": origine,
        })

    rifugi.sort(key=lambda x: (x["comune"], x["nome"]))
    documento = {
        "aggiornato": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totale": len(rifugi),
        "in_attesa": in_attesa,
        "rifugi": rifugi,
    }

    with io.open(USCITA, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=1)
    with io.open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"\nScritti {len(rifugi)} luoghi ({nuovi} geocodificati adesso, "
          f"{in_attesa} in attesa). Durata: {int(time.time() - AVVIO)}s.")
    if in_attesa:
        print("Le segnalazioni rimaste verranno geolocalizzate alla prossima esecuzione.")


if __name__ == "__main__":
    main()
