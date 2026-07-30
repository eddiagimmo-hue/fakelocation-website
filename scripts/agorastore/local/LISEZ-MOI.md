# Veille Agorastore — installation sur votre ordinateur

Une fois installé, votre ordinateur construit le relevé des ventes
immobilières terminées sans aucune enchère et vous l'envoie par courriel
**du lundi au vendredi à 18 h**, sans aucune intervention.

---

## Avant de commencer : le mot de passe d'application Gmail

Le rapport part d'une adresse Gmail. Google **refuse le mot de passe habituel
du compte** pour ce type d'envoi automatique : il faut créer un « mot de passe
d'application », qui ne sert qu'à ça et se révoque à tout moment.

1. Le compte Gmail doit avoir la **validation en deux étapes** active
   ([myaccount.google.com/security](https://myaccount.google.com/security)).
2. Aller sur **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**.
3. Donner un nom quelconque (par exemple « Veille Agorastore ») et valider.
4. Google affiche **16 lettres** en quatre groupes. Gardez-les sous la main :
   l'installateur va les demander. Les espaces n'ont pas d'importance.

---

## Installation

### Sur Mac

1. Placez ce dossier où vous voulez le garder — par exemple dans
   **Documents**. Il ne devra plus être déplacé ensuite.
2. Ouvrez l'application **Terminal** (⌘ + Espace, tapez « Terminal »).
3. Tapez `cd ` (avec l'espace), puis **glissez le dossier** dans la fenêtre
   du Terminal et appuyez sur Entrée.
4. Tapez :

   ```
   ./installer.sh
   ```

Si le Mac répond que Python est introuvable, tapez `xcode-select --install`,
laissez l'installation se faire, puis reprenez à l'étape 4.

### Sur PC Windows

1. Placez ce dossier où vous voulez le garder — par exemple dans
   **Documents**. Il ne devra plus être déplacé ensuite.
2. **Clic droit** sur `installer-windows.ps1` → **Exécuter avec PowerShell**.

Si Windows bloque le script, ouvrez PowerShell et lancez :

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\installer-windows.ps1
```

Python manquant ? Installez-le depuis
[python.org/downloads](https://www.python.org/downloads/) en **cochant
« Add python.exe to PATH »** pendant l'installation.

### Sur Linux

```bash
./installer.sh
```

---

## Ce que fait l'installateur

- crée un environnement Python isolé dans le dossier (rien n'est installé
  ailleurs sur la machine) ;
- demande l'adresse d'envoi et le mot de passe d'application, et les
  enregistre dans un fichier `.env` **lisible par vous seul** ;
- programme l'exécution automatique (launchd sur Mac, cron sur Linux,
  Tâches planifiées sur Windows) ;
- propose un essai immédiat pour vérifier que le courriel arrive bien.

Il peut être relancé sans risque : les identifiants déjà saisis sont
conservés.

---

## Au quotidien

Le rapport arrive vers 18 h 05, l'exécution prenant environ cinq minutes.

**L'ordinateur doit être allumé et connecté à Internet à 18 h.** S'il est
éteint ou en veille, le rapport de la journée est simplement sauté — celui du
lendemain repartira sur des données à jour. C'est la seule vraie limite de
cette installation.

> Si vous préférez que le rapport parte **même ordinateur éteint**, le même
> pipeline peut tourner gratuitement sur les serveurs GitHub : voir le
> [README technique](../README.md), section « Envoi automatique quotidien ».

---

## En cas de problème

Le déroulé de chaque exécution est consigné dans **`veille.log`**, dans ce
dossier. C'est le premier endroit à regarder si un rapport n'arrive pas.

| Message dans le journal | Cause |
|---|---|
| `Authentification SMTP refusée` | mot de passe d'application incorrect, ou mot de passe du compte utilisé à sa place |
| `ECHEC de la construction` | site inaccessible ou hors ligne au moment de l'exécution |
| journal vide à la date du jour | l'ordinateur était éteint ou en veille à 18 h |

Pour relancer un envoi à la main sans attendre 18 h :

- **Mac / Linux** : `./veille_quotidienne.sh`
- **Windows** : double-clic sur `veille_quotidienne.bat`

Pour changer d'adresse ou de mot de passe : supprimez le fichier `.env`,
puis relancez l'installateur.

## Tout arrêter

| Système | Commande |
|---|---|
| Mac | `launchctl unload ~/Library/LaunchAgents/fr.agorastore.veille.plist` |
| Linux | `crontab -e`, puis supprimez la ligne `veille_quotidienne.sh` |
| Windows | `schtasks /Delete /TN "Veille Agorastore" /F` |

Puis supprimez le dossier si vous le souhaitez.
