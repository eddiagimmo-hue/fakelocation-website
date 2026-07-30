import requests
import re
import json
import time
import sys
from datetime import datetime, timezone

import os
_PROXY = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or 'http://127.0.0.1:34629'
PROXIES = {'https': _PROXY}
CA = '/root/.ccr/ca-bundle.crt'
BASE = 'https://www.agorastore-immo.fr'

CATEGORIES = {
    'Appartement': 'appartement',
    'Bureau': 'bureaux',
    'Locaux commerciaux': 'local-commercial',
    'Immeuble': 'immeuble',
    'Maison': 'maison',
    'Terrain': 'terrain',
}

DATE_FROM = datetime(2023, 1, 1, tzinfo=timezone.utc)
# Borne haute = fin de la journee courante, pour que les executions
# quotidiennes prennent automatiquement en compte les ventes du jour.
DATE_TO = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)

session = requests.Session()

def fetch_page(slug, page):
    url = f'{BASE}/ventes-immobilieres/{slug}'
    for attempt in range(5):
        try:
            r = session.get(url, params={'tvt': 4, 'page': page}, proxies=PROXIES,
                             verify=CA, timeout=30,
                             headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                return r.text
            else:
                print(f'  HTTP {r.status_code} on {slug} page {page}, retry {attempt}', file=sys.stderr)
        except Exception as e:
            print(f'  error {e} on {slug} page {page}, retry {attempt}', file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'Failed to fetch {slug} page {page} after retries')


def extract_search_results(html):
    idx = html.find('"searchResults"')
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
        raise RuntimeError('unbalanced braces')
    snippet = html[start:end]
    return json.loads(snippet)


def parse_date(s):
    return datetime.fromisoformat(s)


def scrape_category(display_name, slug):
    results = []
    page = 1
    total = None
    while True:
        html = fetch_page(slug, page)
        data = extract_search_results(html)
        if data is None:
            print(f'  no searchResults found on {slug} page {page}', file=sys.stderr)
            break
        products = data.get('products', [])
        count_total = data.get('countTotal', 0)
        size = data.get('size', 30)
        total = count_total
        if not products:
            break
        for p in products:
            sale = p.get('sale', {})
            end_date_str = sale.get('endDate')
            if not end_date_str:
                continue
            end_date = parse_date(end_date_str)
            total_bids = sale.get('totalBids')
            sale_status = sale.get('saleStatus')
            in_range = DATE_FROM <= end_date <= DATE_TO
            if sale_status == 2 and total_bids == 0 and in_range:
                results.append({
                    'type_de_local': display_name,
                    'ville': p.get('productName'),
                    'prix_mise_en_vente': sale.get('currentPrice'),
                    'end_date': end_date_str,
                    'url': BASE + p.get('productPageUrl', ''),
                    'product_id': p.get('productId'),
                })
        print(f'  {slug} page {page}: {len(products)} products, countTotal={count_total}', file=sys.stderr)
        page += 1
        if page > (total // size) + 2:
            break
        time.sleep(0.5)
    return results


if __name__ == '__main__':
    all_results = []
    for display_name, slug in CATEGORIES.items():
        print(f'Scraping category: {display_name} ({slug})', file=sys.stderr)
        cat_results = scrape_category(display_name, slug)
        print(f'  -> {len(cat_results)} listings with 0 bids in date range', file=sys.stderr)
        all_results.extend(cat_results)

    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f'TOTAL: {len(all_results)} listings', file=sys.stderr)
