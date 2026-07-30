import requests
import re
import json
import time
import sys

import os
_PROXY = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or 'http://127.0.0.1:34629'
PROXIES = {'https': _PROXY}
CA = '/root/.ccr/ca-bundle.crt'

session = requests.Session()

SURFACE_LABELS_PRIORITY = [
    'Surface habitable',
    'Surface Carrez',
    'Surface de plancher',
    'Surface utile',
    'Surface totale',
    'Surface',
]
PARCELLE_LABELS = ['Surface parcelle', 'Surface terrain', 'Surface du terrain']


def extract_array(html, key):
    idx = html.find(f'"{key}"')
    if idx == -1:
        return None
    start = html.find('[', idx)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        return None
    return json.loads(html[start:end])


def parse_m2(value):
    if not value:
        return None
    m = re.search(r'([\d\s .,]+)\s*m', value)
    if not m:
        return None
    num = m.group(1).replace(' ', '').replace(' ', '').replace(',', '.')
    try:
        return float(num)
    except ValueError:
        return None


def fetch(url):
    for attempt in range(5):
        try:
            r = session.get(url, proxies=PROXIES, verify=CA, timeout=30,
                             headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                return r.text
            print(f'  HTTP {r.status_code} on {url}, retry {attempt}', file=sys.stderr)
        except Exception as e:
            print(f'  error {e} on {url}, retry {attempt}', file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


def get_surfaces(html):
    groups = extract_array(html, 'descriptifs')
    labels = {}
    if groups:
        for g in groups:
            for item in g.get('descriptifs', []):
                lib = item.get('descriptifLibelle')
                val = item.get('value')
                if lib and val:
                    labels[lib] = val

    surface = None
    surface_label_used = None
    for lib in SURFACE_LABELS_PRIORITY:
        if lib in labels:
            surface = parse_m2(labels[lib])
            surface_label_used = lib
            break
    # fallback: any label containing 'surface' but not parcelle/terrain
    if surface is None:
        for lib, val in labels.items():
            if re.search(r'surface', lib, re.I) and not re.search(r'parcelle|terrain', lib, re.I):
                s = parse_m2(val)
                if s:
                    surface = s
                    surface_label_used = lib
                    break

    parcelle = None
    parcelle_label_used = None
    for lib in PARCELLE_LABELS:
        if lib in labels:
            parcelle = parse_m2(labels[lib])
            parcelle_label_used = lib
            break

    return surface, surface_label_used, parcelle, parcelle_label_used, labels


if __name__ == '__main__':
    with open('final.json', encoding='utf-8') as f:
        data = json.load(f)

    all_labels_seen = set()
    for i, d in enumerate(data):
        url = d['url']
        html = fetch(url)
        if html is None:
            d['surface_m2'] = None
            d['surface_parcelle_m2'] = None
            continue
        surface, slabel, parcelle, plabel, labels = get_surfaces(html)
        if surface is None and 'Terrain' not in d.get('types', []):
            # Certaines fiches n'ont aucun descriptif de surface batie alors
            # que le titre la porte ("Bureaux - 233 m² - Mulhouse (68)").
            # Sans surface, le prix au m2 serait vide a tort.
            surface = parse_m2(d.get('product_name_detail') or d.get('ville') or '')
            if surface is not None:
                slabel = 'titre'
        d['surface_m2'] = surface
        d['surface_parcelle_m2'] = parcelle
        for lib in labels:
            if re.search(r'surface|parcelle', lib, re.I):
                all_labels_seen.add(lib)
        print(f'[{i+1}/{len(data)}] {d["city"]}: surface={surface} ({slabel}), parcelle={parcelle} ({plabel})', file=sys.stderr)
        time.sleep(0.3)

    print('All surface-related labels seen:', sorted(all_labels_seen), file=sys.stderr)

    missing_surface = [d for d in data if d.get('surface_m2') is None]
    print(f'{len(missing_surface)} listings missing a surface value', file=sys.stderr)
    for d in missing_surface:
        print('  NO SURFACE:', d['url'], file=sys.stderr)

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
