import re
import json
import sys

from net import fetch_text


CITY_RE_POSTAL = re.compile(r'"formattedAddress":"[^"]*?,\s*(\d{5})\s+([^,"]+),\s*France"')
CITY_RE_ADRESSE = re.compile(r'"Adresse","value":"[^"]*?(\d{5})\s+([^",]+?)\s*"')
CITY_RE_NOPOSTAL = re.compile(r'"formattedAddress":"([^",]+),\s*France"')


def clean_city(name):
    """Les pages encodent l'apostrophe en litteral \\u0027 ("Corgnac-sur-l\\u0027Isle").

    Sans ce nettoyage, la recherche de population sur geo.api.gouv.fr echoue
    pour toutes les communes dont le nom comporte une apostrophe.
    """
    return name.replace('\\u0027', "'").strip()


def parse_postal_city(html):
    m = CITY_RE_POSTAL.search(html)
    if m:
        return m.group(1).strip(), clean_city(m.group(2))
    m = CITY_RE_ADRESSE.search(html)
    if m:
        return m.group(1).strip(), clean_city(m.group(2))
    m = CITY_RE_NOPOSTAL.search(html)
    if m:
        return None, clean_city(m.group(1))
    return None, None


def fetch(url):
    return fetch_text(url)


if __name__ == '__main__':
    with open('final.json', encoding='utf-8') as f:
        data = json.load(f)

    for i, d in enumerate(data):
        print(f'[{i+1}/{len(data)}] {d["url"]}', file=sys.stderr)
        html = fetch(d['url'])
        if html is None:
            d['postal_code'] = None
            continue
        postal, city = parse_postal_city(html)
        d['postal_code'] = postal
        if city:
            d['city'] = city

    missing = [d for d in data if not d.get('postal_code')]
    print(f'Done. {len(missing)} missing postal code', file=sys.stderr)
    for d in missing:
        print('MISSING POSTAL:', d['url'], file=sys.stderr)

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
