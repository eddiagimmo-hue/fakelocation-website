#!/usr/bin/env bash
# Pipeline complet : produit annonces_sans_enchere_agorastore.xlsx
#
# Usage : ./run_all.sh
#
# PYTHON_BIN permet de pointer un interpreteur precis (l'installation locale
# passe celui de son environnement virtuel) ; sinon python3 du systeme.
set -euo pipefail

cd "$(dirname "$0")"

# Chaque execution repart de donnees fraiches.
rm -rf .httpcache

PY="${PYTHON_BIN:-python3}"

"$PY" -c "import requests, openpyxl, PIL" 2>/dev/null || {
  echo ">>> Installation des dependances manquantes"
  "$PY" -m pip install --quiet requests openpyxl Pillow
}

echo ">>> 1/7 Recherche des ventes terminees sans enchere"
"$PY" scrape.py

echo ">>> 2/7 Enrichissement depuis les fiches produit"
"$PY" enrich.py

echo ">>> 3/7 Deduplication par produit"
"$PY" dedup.py

echo ">>> 4/7 Codes postaux"
"$PY" add_postal.py

echo ">>> 5/7 Population des communes"
"$PY" get_population.py

echo ">>> 6/7 Surfaces + miniatures"
"$PY" get_surfaces.py
"$PY" get_images.py

echo ">>> 7/7 Generation du classeur Excel"
"$PY" make_xlsx.py

echo ">>> Termine : $(pwd)/annonces_sans_enchere_agorastore.xlsx"
