import re
import json
import sys
import os
from PIL import Image
from io import BytesIO

from net import fetch, fetch_text

IMG_DIR = 'thumbnails'
os.makedirs(IMG_DIR, exist_ok=True)

THUMB_WIDTH = 120  # px


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


def reparer_url(url):
    """Corrige les URLs d'image malformées émises par le site.

    Certaines fiches renvoient « cdn.agorastore.frproduits/images/... » :
    la barre oblique manque après le domaine. Sans correction, chaque
    exécution s'acharne sur un domaine inexistant.
    """
    if url:
        url = url.replace('cdn.agorastore.frproduits/', 'cdn.agorastore.fr/produits/')
    return url


if __name__ == '__main__':
    with open('final.json', encoding='utf-8') as f:
        data = json.load(f)

    for i, d in enumerate(data):
        pid = d['product_id']
        out_path = os.path.join(IMG_DIR, f'{pid}.jpg')
        if os.path.exists(out_path):
            d['thumbnail_path'] = out_path
            print(f'[{i+1}/{len(data)}] {pid}: already downloaded', file=sys.stderr)
            continue
        html = fetch_text(d['url'])
        if html is None:
            d['thumbnail_path'] = None
            continue
        images = extract_array(html, 'images')
        if not images:
            print(f'[{i+1}/{len(data)}] {pid}: aucune image', file=sys.stderr)
            d['thumbnail_path'] = None
            continue
        img_url = reparer_url(images[0].get('urlSmallSize') or images[0].get('url'))
        # L'image finit en vignette sur disque : la mettre aussi en cache
        # HTTP la stockerait deux fois pour rien.
        img_bytes = fetch(img_url, cache=False, retries=2)
        if img_bytes is None:
            d['thumbnail_path'] = None
            continue
        try:
            im = Image.open(BytesIO(img_bytes)).convert('RGB')
            ratio = THUMB_WIDTH / im.width
            new_size = (THUMB_WIDTH, max(1, int(im.height * ratio)))
            im = im.resize(new_size)
            im.save(out_path, 'JPEG', quality=80)
            d['thumbnail_path'] = out_path
            d['thumbnail_width'] = new_size[0]
            d['thumbnail_height'] = new_size[1]
            print(f'[{i+1}/{len(data)}] {pid}: saved {new_size}', file=sys.stderr)
        except Exception as e:
            print(f'[{i+1}/{len(data)}] {pid}: error processing image {e}', file=sys.stderr)
            d['thumbnail_path'] = None


    missing = [d for d in data if not d.get('thumbnail_path')]
    print(f'Done. {len(missing)} missing thumbnails', file=sys.stderr)
    for d in missing:
        print('  NO THUMBNAIL:', d['url'], file=sys.stderr)

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
