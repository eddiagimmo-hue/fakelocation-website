#!/usr/bin/env bash
# Installation de la veille Agorastore sur un Mac ou un PC Linux.
#
# À lancer une seule fois :  ./installer.sh
#
# Met en place un environnement Python isolé, demande les identifiants
# d'envoi, puis programme l'exécution du lundi au vendredi à 18 h.
set -euo pipefail

DOSSIER="$(cd "$(dirname "$0")" && pwd)"
cd "$DOSSIER"

echo
echo "  Veille Agorastore — installation"
echo "  ================================"
echo

# ---------------------------------------------------------------- Python ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 est introuvable."
  echo
  echo "  macOS   : ouvrez le Terminal et tapez  xcode-select --install"
  echo "  Linux   : sudo apt install python3 python3-venv"
  echo
  exit 1
fi
echo "Python détecté : $(python3 --version)"

echo "Création de l'environnement isolé..."
python3 -m venv .venv 2>/dev/null || {
  echo
  echo "La création a échoué. Sur Debian/Ubuntu, installez d'abord :"
  echo "  sudo apt install python3-venv"
  exit 1
}
PYTHON="$DOSSIER/.venv/bin/python3"

echo "Installation des bibliothèques (une minute environ)..."
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet requests openpyxl Pillow
echo "  fait."

# ------------------------------------------------------------ Identifiants ---
if [ -f .env ]; then
  echo
  echo "Un fichier .env existe déjà, les identifiants sont conservés."
  echo "Pour les changer : supprimez .env puis relancez ce script."
else
  cat <<'TEXTE'

  Envoi du rapport
  ----------------
  Le rapport part d'une adresse Gmail vers ed.diagimmo@gmail.com.

  Gmail refuse le mot de passe habituel du compte pour ce type d'envoi.
  Il faut un « mot de passe d'application », qui se crée ici :

      https://myaccount.google.com/apppasswords

  (la validation en deux étapes doit être active sur le compte)
  C'est une suite de 16 lettres, que vous pouvez coller avec ou sans espaces.

TEXTE

  read -rp "  Adresse Gmail qui envoie : " SMTP_USER
  read -rsp "  Mot de passe d'application : " SMTP_PASSWORD
  echo
  read -rp "  Adresse qui reçoit [ed.diagimmo@gmail.com] : " MAIL_TO
  MAIL_TO="${MAIL_TO:-ed.diagimmo@gmail.com}"

  # Gmail affiche le mot de passe par groupes de quatre ; les espaces
  # collés depuis la page Google feraient échouer l'authentification.
  SMTP_PASSWORD="${SMTP_PASSWORD// /}"

  umask 077
  cat > .env <<FIN
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
MAIL_TO=$MAIL_TO
FIN
  chmod 600 .env
  echo
  echo "  Identifiants enregistrés dans .env (lisible par vous seul)."
fi

chmod +x veille_quotidienne.sh run_all.sh 2>/dev/null || true

# ------------------------------------------------------------ Planification ---
echo
echo "Programmation de l'exécution automatique..."

case "$(uname -s)" in
  Darwin)
    ETIQUETTE="fr.agorastore.veille"
    PLIST="$HOME/Library/LaunchAgents/$ETIQUETTE.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<FIN
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ETIQUETTE</string>
  <key>ProgramArguments</key>
  <array><string>$DOSSIER/veille_quotidienne.sh</string></array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  </array>
</dict>
</plist>
FIN
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "  Programmé via launchd (lun-ven, 18 h)."
    echo "  Pour arrêter :  launchctl unload $PLIST"
    ;;

  Linux)
    if command -v crontab >/dev/null 2>&1; then
      LIGNE="0 18 * * 1-5 $DOSSIER/veille_quotidienne.sh"
      # On retire une éventuelle ligne précédente avant de réécrire.
      (crontab -l 2>/dev/null | grep -v -F "veille_quotidienne.sh" || true;
       echo "$LIGNE") | crontab -
      echo "  Programmé via cron (lun-ven, 18 h)."
      echo "  Pour arrêter :  crontab -e  puis supprimez la ligne veille_quotidienne.sh"
    else
      # Sans cron, tout le reste fonctionne : seule la programmation manque.
      echo "  cron n'est pas installé sur ce système."
      echo "  Installez-le (sudo apt install cron) puis relancez ce script,"
      echo "  ou ajoutez vous-même cette ligne via « crontab -e » :"
      echo
      echo "      0 18 * * 1-5 $DOSSIER/veille_quotidienne.sh"
    fi
    ;;

  *)
    echo "  Système non reconnu ($(uname -s))."
    echo "  Sous Windows, utilisez plutôt installer-windows.ps1."
    ;;
esac

# ------------------------------------------------------------------ Essai ---
cat <<'TEXTE'

  Installation terminée.

  Le rapport partira automatiquement du lundi au vendredi à 18 h,
  à condition que l'ordinateur soit allumé et connecté à cette heure-là.

TEXTE

read -rp "  Faire un essai maintenant ? (environ 5 min) [o/N] " ESSAI
case "$ESSAI" in
  [oOyY]*)
    echo
    ./veille_quotidienne.sh && {
      echo
      echo "  Envoyé. Vérifiez votre boîte de réception."
    } || {
      echo
      echo "  L'essai a échoué. Le détail est dans veille.log :"
      tail -n 20 veille.log
    }
    ;;
  *)
    echo "  Vous pourrez tester plus tard avec :  ./veille_quotidienne.sh"
    ;;
esac
echo
