"""Envoie le classeur par e-mail — remplace la livraison via Claude.

Configuration par variables d'environnement, jamais en dur dans le dépôt :

    MAIL_TO         destinataire (obligatoire)
    SMTP_USER       compte SMTP (obligatoire)
    SMTP_PASSWORD   mot de passe d'application (obligatoire)
    SMTP_HOST       défaut smtp.gmail.com
    SMTP_PORT       défaut 587 (STARTTLS) ; 465 bascule en SSL implicite
    MAIL_FROM       défaut = SMTP_USER

Avec Gmail, `SMTP_PASSWORD` doit être un **mot de passe d'application**
(https://myaccount.google.com/apppasswords), pas le mot de passe du compte :
Google refuse les connexions SMTP avec ce dernier.

Usage :
    python3 send_email.py annonces_sans_enchere_agorastore.xlsx
"""
import os
import smtplib
import ssl
import sys
from datetime import date
from email.message import EmailMessage
from pathlib import Path

XLSX_MIME = ('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def env(name, default=None):
    """Comme os.environ.get, mais une valeur vide vaut « non définie ».

    GitHub Actions transmet les variables non renseignées sous forme de
    chaîne vide : sans cela, `SMTP_PORT` absent donnerait `int('')`.
    """
    value = os.environ.get(name, '').strip()
    return value or default


def build_message(path: Path, rows: int | None) -> EmailMessage:
    today = date.today().strftime('%d/%m/%Y')
    msg = EmailMessage()
    msg['Subject'] = f'Agorastore — ventes sans enchère au {today}'
    msg['From'] = env('MAIL_FROM') or env('SMTP_USER')
    msg['To'] = env('MAIL_TO')

    total = f'{rows} annonces' if rows is not None else 'Le relevé'
    msg.set_content(
        f"Bonjour,\n\n"
        f"Ci-joint le relevé des ventes immobilières terminées sur "
        f"agorastore-immo.fr n'ayant reçu aucune enchère, à jour au {today}.\n\n"
        f"{total} depuis le 1er janvier 2023, réparties en un onglet par année.\n\n"
        f"Message automatique.\n"
    )

    msg.add_attachment(path.read_bytes(), maintype=XLSX_MIME[0],
                       subtype=XLSX_MIME[1], filename=path.name)
    return msg


def count_rows() -> int | None:
    """Nombre d'annonces, lu depuis final.json s'il est disponible."""
    try:
        import json
        with open('final.json', encoding='utf-8') as f:
            return len(json.load(f))
    except Exception:
        return None


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1
                else 'annonces_sans_enchere_agorastore.xlsx')
    if not path.is_file():
        print(f'Fichier introuvable : {path}', file=sys.stderr)
        return 1

    missing = [k for k in ('MAIL_TO', 'SMTP_USER', 'SMTP_PASSWORD')
               if not env(k)]
    if missing:
        print('Variables manquantes : ' + ', '.join(missing), file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2

    host = env('SMTP_HOST', 'smtp.gmail.com')
    port = int(env('SMTP_PORT', '587'))
    msg = build_message(path, count_rows())

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as s:
                s.login(env('SMTP_USER'), env('SMTP_PASSWORD'))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=60) as s:
                s.starttls(context=context)
                s.login(env('SMTP_USER'), env('SMTP_PASSWORD'))
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print('Authentification SMTP refusée. Avec Gmail, utilisez un mot de '
              'passe d\'application, pas le mot de passe du compte.',
              file=sys.stderr)
        return 3

    print(f'Envoyé à {msg["To"]} ({path.name}, {path.stat().st_size // 1024} Ko)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
