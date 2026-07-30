"""Deduplique enriched.json par product_id vers final.json.

Un meme bien peut apparaitre dans plusieurs categories (ex. "Bureau" et
"Immeuble"). On garde une seule ligne par produit en accumulant les
categories dans le champ `types`.
"""
import json
from collections import OrderedDict

with open('enriched.json', encoding='utf-8') as f:
    data = json.load(f)

by_id = OrderedDict()
for d in data:
    pid = d['product_id']
    if pid not in by_id:
        by_id[pid] = dict(d)
        by_id[pid]['types'] = [d['type_de_local']]
    elif d['type_de_local'] not in by_id[pid]['types']:
        by_id[pid]['types'].append(d['type_de_local'])

# Les pages produit encodent parfois l'apostrophe en litteral "'".
for d in by_id.values():
    for key in ('city', 'product_name_detail'):
        if isinstance(d.get(key), str):
            d[key] = d[key].replace('\\u0027', "'")

with open('final.json', 'w', encoding='utf-8') as f:
    json.dump(list(by_id.values()), f, ensure_ascii=False, indent=2)

print(f'{len(data)} lignes -> {len(by_id)} produits uniques')
missing_city = [d for d in by_id.values() if not d.get('city')]
if missing_city:
    print(f'ATTENTION: {len(missing_city)} sans ville')
