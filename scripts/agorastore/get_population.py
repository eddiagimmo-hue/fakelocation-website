import requests
import difflib
import json
import time
import sys

import os
_PROXY = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or 'http://127.0.0.1:34629'
PROXIES = {'https': _PROXY}
CA = '/root/.ccr/ca-bundle.crt'

session = requests.Session()


def _api(params):
    try:
        r = session.get('https://geo.api.gouv.fr/communes', params=params,
                         proxies=PROXIES, verify=CA, timeout=20)
        return r.json()
    except Exception as e:
        print(f'  error querying {params}: {e}', file=sys.stderr)
        return []


def _by_postal_code(city, postal_code):
    """Repli quand le nom est inconnu de l'API (commune fusionnee/renommee).

    Ex. "Neussargues en Pinatelle" est enregistree "Neussargues-Moissac".
    On liste les communes du code postal et on retient celle dont le nom
    ressemble le plus.
    """
    results = _api({'codePostal': postal_code, 'fields': 'nom,population,codesPostaux'})
    if not results:
        return None, None
    names = [r.get('nom', '') for r in results]
    close = difflib.get_close_matches(city, names, n=1, cutoff=0.4)
    if not close:
        # Dernier recours : premier token du nom (ex. "Neussargues").
        token = city.split()[0].split('-')[0].lower()
        close = [n for n in names if n.lower().startswith(token)]
        if not close:
            return None, None
    match = next(r for r in results if r.get('nom') == close[0])
    return match.get('population'), match.get('nom')


def query_population(city, postal_code):
    dept = postal_code[:2] if postal_code else None
    results = _api({'nom': city, 'fields': 'nom,population,codesPostaux', 'boost': 'population'})

    if not results:
        return _by_postal_code(city, postal_code) if postal_code else (None, None)

    def dept_match(res):
        if not dept:
            return False
        return any(cp.startswith(dept) for cp in res.get('codesPostaux', []))

    def name_match(res):
        return res.get('nom', '').strip().lower() == city.strip().lower()

    exact_and_dept = [r for r in results if name_match(r) and dept_match(r)]
    exact_only = [r for r in results if name_match(r)]
    dept_only = [r for r in results if dept_match(r)]

    for pool in (exact_and_dept, exact_only, dept_only):
        if pool:
            pool = sorted(pool, key=lambda r: r.get('population') or 0, reverse=True)
            top = pool[0]
            return top.get('population'), top.get('nom')

    # Aucun candidat du bon departement ni du bon nom : la recherche par nom
    # a repondu autre chose. On repasse par le code postal.
    if postal_code:
        pop, name = _by_postal_code(city, postal_code)
        if pop is not None:
            return pop, name
    return None, None


if __name__ == '__main__':
    with open('final.json', encoding='utf-8') as f:
        data = json.load(f)

    for i, d in enumerate(data):
        city = d.get('city')
        postal = d.get('postal_code')
        pop, matched_name = query_population(city, postal)
        d['population'] = pop
        print(f'[{i+1}/{len(data)}] {city} ({postal}) -> pop={pop} (matched: {matched_name})', file=sys.stderr)
        time.sleep(0.3)

    missing = [d for d in data if d.get('population') is None]
    print(f'Done. {len(missing)} missing population', file=sys.stderr)
    for d in missing:
        print('MISSING POP:', d['city'], d['postal_code'], d['url'], file=sys.stderr)

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
