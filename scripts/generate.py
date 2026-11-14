"""Teamantix — génère les codes d'équipe et les écrit chiffrés dans codes.json.

Lancé plusieurs fois par jour par GitHub Actions (les jeux ne changent pas de jour
à la même heure). Un code n'est recréé que si le numéro du jour de ce jeu a changé.
Variable d'environnement requise :
  TEAM_PASSPHRASE : phrase secrète partagée avec la team.
"""
import base64
import json
import os
import random
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Secours si le site ne répond pas : numéros relevés le 13/11/2026 à 16:07 (Paris),
# +1 à chaque bascule du jeu (heure de Paris) — mêmes réglages que index.html.
PARIS = ZoneInfo("Europe/Paris")
ANCHOR = datetime(2026, 11, 13, 16, 7, tzinfo=PARIS)

# jeu: (numéro au 13/11 16h07, heure de bascule à Paris, page du jeu, base Firebase)
GAMES = {
    "pedantle": (1639, 21, "https://pedantle.certitudes.org/",
                 "https://pedantle-c5c98-default-rtdb.firebaseio.com"),
    "cemantle": (1684, 9, "https://cemantle.certitudes.org/",
                 "https://cemantle-default-rtdb.firebaseio.com"),
    "cemantix": (1717, 0, "https://cemantix.certitudes.org/",
                 "https://cemantix-11e28-default-rtdb.europe-west1.firebasedatabase.app"),
    "pedantix": (1644, 0, "https://pedantix.certitudes.org/",
                 "https://pedantix-32f5c-default-rtdb.europe-west1.firebasedatabase.app"),
}

PBKDF2_ITER = 200_000
PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def day_index(dt: datetime, reset_hour: int) -> int:
    """Numéro de "jour de jeu" : date locale à Paris, décalée de l'heure de bascule."""
    return (dt.astimezone(PARIS).replace(tzinfo=None) - timedelta(hours=reset_hour)).toordinal()


def today_num(ref: int, reset_hour: int) -> int:
    now = datetime.now(timezone.utc)
    return ref + day_index(now, reset_hour) - day_index(ANCHOR, reset_hour)


def site_num(url: str) -> int:
    """Lit data-puzzle-number directement sur la page du jeu."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'data-puzzle-number="(\d+)"', html)
    if not m:
        raise RuntimeError("numéro introuvable dans la page")
    return int(m.group(1))


def push_id() -> str:
    """Clé au format Firebase push() : 8 caractères d'horodatage + 12 aléatoires."""
    now = int(time.time() * 1000)
    ts = ""
    for _ in range(8):
        ts = PUSH_CHARS[now % 64] + ts
        now //= 64
    rnd = "".join(random.SystemRandom().choice(PUSH_CHARS) for _ in range(12))
    return ts + rnd


def http(method: str, url: str, body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"null")


def create_team(db: str, n: int) -> str:
    key = push_id()
    # Identique au bouton Start : g/<n>/<clé>/_users = 1
    http("PUT", f"{db}/g/{n}/{key}/_users.json", b"1")
    if http("GET", f"{db}/g/{n}/{key}/_users.json") != 1:
        raise RuntimeError("équipe absente après écriture")
    return key.replace("-", "Ô")


def derive(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=iterations).derive(passphrase.encode())


def load_previous(passphrase: str) -> dict:
    """Déchiffre le codes.json existant (s'il y en a un) pour réutiliser les codes encore valides."""
    try:
        with open("codes.json", encoding="utf-8") as f:
            enc = json.load(f)
        key = derive(passphrase, base64.b64decode(enc["salt"]), enc["iter"])
        pt = AESGCM(key).decrypt(base64.b64decode(enc["iv"]), base64.b64decode(enc["data"]), None)
        return json.loads(pt).get("codes", {})
    except Exception as e:
        print(f"Pas de codes précédents utilisables ({e})")
        return {}


def encrypt(payload: dict, passphrase: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    key = derive(passphrase, salt, PBKDF2_ITER)
    ct = AESGCM(key).encrypt(iv, json.dumps(payload).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": PBKDF2_ITER, "salt": b64(salt), "iv": b64(iv), "data": b64(ct)}


def main():
    passphrase = os.environ["TEAM_PASSPHRASE"]
    previous = load_previous(passphrase)
    codes, changed = {}, False
    for game, (ref, reset, url, db) in GAMES.items():
        try:
            n, how = site_num(url), "site"
        except Exception as e:
            n, how = today_num(ref, reset), f"calcul (site KO : {e})"
        old = previous.get(game, {})
        if old.get("num") == n and old.get("code"):
            codes[game] = old
            print(f"{game}: jour n° {n} via {how} — code inchangé")
            continue
        changed = True
        try:
            codes[game] = {"num": n, "code": create_team(db, n),
                           "since": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print(f"{game}: jour n° {n} via {how} — nouveau code")
        except Exception as e:  # on publie quand même les autres jeux
            codes[game] = {"num": n, "error": str(e)}
            print(f"{game}: jour n° {n} via {how} — ERREUR {e}")

    if not changed:
        print("Aucun jeu n'a changé de jour : codes.json non modifié.")
        return

    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "codes": codes}
    out = {"generated": payload["generated"], **encrypt(payload, passphrase)}
    with open("codes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
