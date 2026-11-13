"""Teamantix — génère les codes d'équipe du jour et les écrit chiffrés dans codes.json.

Lancé chaque jour par GitHub Actions. Variable d'environnement requise :
  TEAM_PASSPHRASE : phrase secrète partagée avec la team.
"""
import base64
import json
import os
import random
import time
import urllib.request
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Numéros relevés le 13/11/2026 à 15:07 UTC ; +1 à chaque 01:00 UTC
ANCHOR = datetime(2026, 11, 13, 15, 7, tzinfo=timezone.utc).timestamp()
RESET_SEC = 3600

GAMES = {
    "pedantle": (1639, "https://pedantle-c5c98-default-rtdb.firebaseio.com"),
    "cemantle": (1684, "https://cemantle-default-rtdb.firebaseio.com"),
    "cemantix": (1717, "https://cemantix-11e28-default-rtdb.europe-west1.firebasedatabase.app"),
    "pedantix": (1645, "https://pedantix-32f5c-default-rtdb.europe-west1.firebasedatabase.app"),
}

PBKDF2_ITER = 200_000
PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def day_index(t: float) -> int:
    return int((t - RESET_SEC) // 86400)


def today_num(ref: int) -> int:
    return ref + day_index(time.time()) - day_index(ANCHOR)


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


def encrypt(payload: dict, passphrase: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITER).derive(passphrase.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(payload).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": PBKDF2_ITER, "salt": b64(salt), "iv": b64(iv), "data": b64(ct)}


def main():
    passphrase = os.environ["TEAM_PASSPHRASE"]
    codes = {}
    for game, (ref, db) in GAMES.items():
        n = today_num(ref)
        try:
            codes[game] = {"num": n, "code": create_team(db, n)}
            print(f"{game} #{n}: OK")
        except Exception as e:  # on publie quand même les autres jeux
            codes[game] = {"num": n, "error": str(e)}
            print(f"{game} #{n}: ERREUR {e}")

    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "codes": codes}
    out = {"generated": payload["generated"], **encrypt(payload, passphrase)}
    with open("codes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
