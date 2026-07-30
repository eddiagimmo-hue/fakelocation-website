import requests
import re
import json
import time
import sys
import os
from PIL import Image
from io import BytesIO

import os
_PROXY = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or 'http://127.0.0.1:34629'
PROXIES = {'https': _PROXY}
CA = '/root/.ccr/ca-bundle.crt'

session = requests.Session()
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


def fetch(url):
    for attempt in range(5):
        try:
            r = session.get(url, proxies=PROXIES, verify=CA, timeout=30,
                             headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                return r
            print(f'  HTTP {r.status_code} on {url}, retry {attempt}', file=sys.stderr)
        except Exception as e:
            print(f'  error {e} on {url}, retry {attempt}', file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


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
        r = fetch(d['url'])
        if r is None:
            d['thumbnail_path'] = None
            continue
        images = extract_array(r.text, 'images')
        if not images:
            print(f'[{i+1}/{len(data)}] {pid}: NO IMAGES FOUND', file=sys.stderr)
            d['thumbnail_path'] = None
            continue
        img_url = images[0].get('urlSmallSize') or images[0].get('url')
        img_resp = fetch(img_url)
        if img_resp is None:
            d['thumbnail_path'] = None
            continue
        try:
            im = Image.open(BytesIO(img_resp.content)).convert('RGB')
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
        time.sleep(0.3)

    missing = [d for d in data if not d.get('thumbnail_path')]
    print(f'Done. {len(missing)} missing thumbnails', file=sys.stderr)
    for d in missing:
        print('  NO THUMBNAIL:', d['url'], file=sys.stderr)

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
