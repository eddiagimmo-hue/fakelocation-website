"""Accès réseau partagé par les scripts du pipeline.

Deux rôles :

1. **Portabilité.** Fonctionne en connexion directe (machine ordinaire,
   runner CI) comme derrière un proxy qui re-signe le TLS : les variables
   `HTTPS_PROXY` et `REQUESTS_CA_BUNDLE` sont prises en compte si elles
   existent. Aucune configuration n'est nécessaire dans le premier cas.

2. **Cache disque.** Quatre étapes du pipeline ont besoin de la même fiche
   produit. Sans cache, chaque exécution quotidienne téléchargerait quatre
   fois les mêmes ~90 pages. Le cache les ramène à une seule requête.
   `run_all.sh` le vide au démarrage pour que chaque exécution reparte de
   données fraîches.
"""
import hashlib
import os
import sys
import time
from pathlib import Path

import requests

_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
PROXIES = {'https': _proxy} if _proxy else None

# `verify=True` = magasin de certificats système, le cas normal.
_ca = os.environ.get('REQUESTS_CA_BUNDLE') or '/root/.ccr/ca-bundle.crt'
VERIFY = _ca if os.path.exists(_ca) else True

CACHE_DIR = Path(__file__).with_name('.httpcache')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

_session = requests.Session()


def _cache_path(url: str) -> Path:
    return CACHE_DIR / hashlib.sha256(url.encode()).hexdigest()


def fetch(url, *, cache=True, retries=5, pause=0.3):
    """Renvoie le corps de la réponse en octets, ou None après échec.

    Une réponse servie depuis le cache ne provoque aucune attente ; c'est ce
    qui rend les étapes suivantes du pipeline quasi instantanées.
    """
    path = _cache_path(url)
    if cache and path.is_file():
        return path.read_bytes()

    for attempt in range(retries):
        try:
            r = _session.get(url, proxies=PROXIES, verify=VERIFY, timeout=30,
                             headers=HEADERS)
            if r.status_code == 200:
                if cache:
                    CACHE_DIR.mkdir(exist_ok=True)
                    path.write_bytes(r.content)
                if pause:
                    time.sleep(pause)
                return r.content
            print(f'  HTTP {r.status_code} sur {url} (essai {attempt + 1})',
                  file=sys.stderr)
        except Exception as e:
            print(f'  erreur {e} sur {url} (essai {attempt + 1})',
                  file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


def fetch_text(url, **kw):
    """Idem `fetch`, décodé en UTF-8."""
    body = fetch(url, **kw)
    return body.decode('utf-8', errors='replace') if body is not None else None
