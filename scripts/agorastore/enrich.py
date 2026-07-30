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

def extract_balanced(html, key):
    idx = html.find(f'"{key}"')
    if idx == -1:
        return None
    start = html.find('{', idx)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == '{':
            depth += 1
        elif html[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        return None
    return json.loads(html[start:end])


def fetch_detail(url):
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


CITY_RE_POSTAL = re.compile(r'"formattedAddress":"[^"]*?,\s*\d{5}\s+([^,"]+),\s*France"')
CITY_RE_NOPOSTAL = re.compile(r'"formattedAddress":"([^",]+),\s*France"')
CITY_RE_ADRESSE = re.compile(r'"Adresse","value":"[^"]*?\d{5}\s+([^",]+)"')

def parse_city(html):
    m = CITY_RE_POSTAL.search(html)
    if m:
        return m.group(1).strip()
    m = CITY_RE_ADRESSE.search(html)
    if m:
        return m.group(1).strip()
    m = CITY_RE_NOPOSTAL.search(html)
    if m:
        return m.group(1).strip()
    return None


if __name__ == '__main__':
    with open('results.json', encoding='utf-8') as f:
        candidates = json.load(f)

    enriched = []
    for i, cand in enumerate(candidates):
        url = cand['url']
        print(f'[{i+1}/{len(candidates)}] {url}', file=sys.stderr)
        html = fetch_detail(url)
        if html is None:
            cand['city'] = None
            cand['initial_price'] = None
            cand['bids_count_confirmed'] = None
            enriched.append(cand)
            continue
        sale_state = extract_balanced(html, 'saleState')
        city = parse_city(html)
        if sale_state:
            cand['initial_price'] = sale_state.get('initialPrice')
            cand['bids_count_confirmed'] = sale_state.get('bidsCount')
            cand['product_name_detail'] = sale_state.get('productName')
        else:
            cand['initial_price'] = None
            cand['bids_count_confirmed'] = None
        cand['city'] = city
        enriched.append(cand)
        time.sleep(0.4)

    with open('enriched.json', 'w', encoding='utf-8') as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    mismatches = [e for e in enriched if e.get('bids_count_confirmed') not in (0, None)]
    print(f'Done. {len(enriched)} enriched, {len(mismatches)} bid-count mismatches', file=sys.stderr)
    for m in mismatches:
        print('MISMATCH:', m['url'], m.get('bids_count_confirmed'), file=sys.stderr)
