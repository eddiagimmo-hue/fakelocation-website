#!/usr/bin/env bash
# Appelé chaque jour par le planificateur (cron, launchd ou Tâches planifiées).
#
# Enchaîne la construction du classeur et son envoi, en journalisant tout
# dans veille.log — c'est ce fichier qu'il faut regarder si un matin le
# rapport n'est pas arrivé.
set -uo pipefail

DOSSIER="$(cd "$(dirname "$0")" && pwd)"
cd "$DOSSIER"

JOURNAL="$DOSSIER/veille.log"
exec >> "$JOURNAL" 2>&1

echo
echo "======== $(date '+%d/%m/%Y %H:%M:%S') ========"

# Identifiants SMTP, créés par installer.sh (jamais dans le dépôt).
if [ -f "$DOSSIER/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$DOSSIER/.env"
  set +a
else
  echo "ERREUR : .env introuvable. Relancez ./installer.sh"
  exit 1
fi

PYTHON="$DOSSIER/.venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
  echo "ERREUR : environnement Python absent. Relancez ./installer.sh"
  exit 1
fi

echo "--- Construction du classeur ---"
if ! PYTHON_BIN="$PYTHON" ./run_all.sh; then
  echo "ECHEC de la construction, aucun envoi."
  exit 1
fi

echo "--- Envoi du courriel ---"
if ! "$PYTHON" send_email.py; then
  echo "ECHEC de l'envoi. Le classeur reste disponible dans $DOSSIER"
  exit 1
fi

echo "Terminé."

# Le journal ne doit pas grossir indéfiniment : on garde les 2000 dernières lignes.
if [ "$(wc -l < "$JOURNAL")" -gt 2000 ]; then
  tail -n 2000 "$JOURNAL" > "$JOURNAL.tmp" && mv "$JOURNAL.tmp" "$JOURNAL"
fi
