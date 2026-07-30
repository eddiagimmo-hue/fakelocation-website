#!/usr/bin/env bash
# Pipeline complet : produit annonces_sans_enchere_agorastore.xlsx
#
# Usage : ./run_all.sh
# Les scripts lisent le proxy via $HTTPS_PROXY, il n'y a rien a modifier
# quand le port du proxy change entre deux sessions.
set -euo pipefail

cd "$(dirname "$0")"

python3 -c "import requests, openpyxl, PIL" 2>/dev/null || {
  echo ">>> Installation des dependances manquantes"
  pip install --quiet requests openpyxl Pillow
}

echo ">>> 1/7 Recherche des ventes terminees sans enchere"
python3 scrape.py

echo ">>> 2/7 Enrichissement depuis les fiches produit"
python3 enrich.py

echo ">>> 3/7 Deduplication par produit"
python3 dedup.py

echo ">>> 4/7 Codes postaux"
python3 add_postal.py

echo ">>> 5/7 Population des communes"
python3 get_population.py

echo ">>> 6/7 Surfaces + miniatures"
python3 get_surfaces.py
python3 get_images.py

echo ">>> 7/7 Generation du classeur Excel"
python3 make_xlsx.py

echo ">>> Termine : $(pwd)/annonces_sans_enchere_agorastore.xlsx"
