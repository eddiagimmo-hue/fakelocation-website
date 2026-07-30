# Veille Agorastore-Immo — ventes terminées sans aucune enchère

Produit `annonces_sans_enchere_agorastore.xlsx` : toutes les ventes immobilières
terminées sur [agorastore-immo.fr](https://www.agorastore-immo.fr) depuis le
1<sup>er</sup> janvier 2023 qui n'ont reçu **aucune enchère**.

## Lancer à la main

```bash
./run_all.sh
```

Aucune configuration : les dépendances (`requests`, `openpyxl`, `Pillow`) sont
installées au besoin, et la connexion est directe. Compte environ 5 minutes.

## Envoi automatique quotidien

Le workflow [`agorastore-daily.yml`](../../.github/workflows/agorastore-daily.yml)
exécute le pipeline **du lundi au vendredi à 18 h (heure de Paris)** sur les
serveurs GitHub, puis envoie le classeur par e-mail. Rien à installer, aucune
machine à laisser allumée.

GitHub planifie en UTC, qui ne suit pas l'heure d'été. Le workflow se déclenche
donc à 16 h **et** 17 h UTC, et abandonne aussitôt celle des deux qui ne
correspond pas à 18 h à Paris — l'envoi reste à la même heure locale toute
l'année.

### Mise en service

Dans **Settings → Secrets and variables → Actions** du dépôt, onglet
*Secrets*, créer :

| Secret | Valeur |
|---|---|
| `MAIL_TO` | l'adresse qui reçoit le classeur |
| `SMTP_USER` | l'adresse d'envoi (ex. un compte Gmail) |
| `SMTP_PASSWORD` | un **mot de passe d'application**, voir ci-dessous |

Avec Gmail, `SMTP_PASSWORD` ne doit **pas** être le mot de passe du compte :
Google le refuse en SMTP. Il faut générer un mot de passe d'application sur
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
(la validation en deux étapes doit être active sur le compte).

Pour un autre fournisseur que Gmail, ajouter dans l'onglet *Variables* :
`SMTP_HOST` et, si besoin, `SMTP_PORT` (587 par défaut, STARTTLS ; 465 bascule
en SSL implicite).

### Vérifier

Onglet **Actions → Veille Agorastore → Run workflow** déclenche un envoi
immédiat sans attendre 18 h. Le classeur est aussi déposé en pièce jointe du
run pendant 30 jours, ce qui permet de le récupérer même si l'envoi SMTP échoue.

### En local plutôt que sur GitHub

Si vous préférez faire tourner le pipeline sur votre propre machine, via `cron`
(elle doit être allumée à 18 h) :

```cron
0 18 * * 1-5  cd /chemin/vers/scripts/agorastore && ./run_all.sh && \
              MAIL_TO=… SMTP_USER=… SMTP_PASSWORD=… python3 send_email.py
```

### Derrière un proxy d'entreprise

`net.py` prend en compte `HTTPS_PROXY` et `REQUESTS_CA_BUNDLE` s'ils sont
définis. Sans eux, la connexion est directe et les certificats système sont
utilisés — le cas normal.

## Le classeur produit

Un onglet `Resume` puis un onglet par année. Colonnes :

| Colonne | Source |
|---|---|
| Miniature | 1<sup>re</sup> photo de l'annonce, réduite à 120 px de large |
| Date de fin de vente | `sale.endDate` |
| Type de local | catégorie(s) du site ; un bien peut en cumuler deux |
| Code postal / Ville | adresse de la fiche produit |
| Habitants | population INSEE via [geo.api.gouv.fr](https://geo.api.gouv.fr) |
| Prix de la mise en vente | `saleState.initialPrice` |
| Prix au m² | prix ÷ surface bâtie — vide pour les terrains nus |
| Surface | surface bâtie (habitable, Carrez ou plancher selon la fiche) |
| Surface parcelle extérieure | terrain / parcelle quand renseigné |
| URL | lien cliquable vers l'annonce |

Tri par population de la commune, décroissant.

## Les étapes

| Script | Rôle |
|---|---|
| `net.py` | accès réseau commun : proxy optionnel et cache disque |
| `scrape.py` | parcourt les 6 catégories immobilières, retient `totalBids == 0` et `saleStatus == 2` (terminée) |
| `enrich.py` | ouvre chaque fiche produit : prix de mise à prix, ville, re-vérification du nombre d'enchères |
| `dedup.py` | un bien listé dans deux catégories ne doit produire qu'une ligne |
| `add_postal.py` | code postal + ville normalisée |
| `get_population.py` | population de la commune |
| `get_surfaces.py` | surface bâtie et surface de parcelle |
| `get_images.py` | télécharge et réduit les miniatures |
| `make_xlsx.py` | assemble le classeur |
| `send_email.py` | envoie le classeur en pièce jointe |

Quatre étapes ont besoin de la même fiche produit. `net.py` les met en cache
dans `.httpcache/`, ce qui ramène ~360 requêtes à ~90 : le site n'est
interrogé qu'une fois par annonce et par exécution. `run_all.sh` vide ce cache
au démarrage pour que chaque exécution reparte de données fraîches.

## Comment le site est interrogé

Les pages de résultats embarquent leur JSON dans le HTML — il n'y a pas d'API
publique à appeler. `scrape.py` lit le bloc `searchResults` de
`/ventes-immobilieres/{catégorie}?tvt=4&page=N`, où `tvt=4` filtre les ventes
terminées. Les fiches produit exposent de même `saleState`, `descriptifs` et
`images`.

Ces clés appartiennent au site et peuvent changer sans préavis. Les scripts
signalent alors des champs manquants plutôt que d'échouer : surveiller les
lignes `missing` / `NO SURFACE` / `ATTENTION` en sortie.

## Points de vigilance

- **Terrains nus** : pas de surface bâtie, donc pas de prix au m². Leur
  superficie est en « Surface parcelle extérieure ».
- **Communes fusionnées ou renommées** : `get_population.py` retombe sur une
  recherche par code postal (ex. « Neussargues en Pinatelle » est enregistrée
  « Neussargues-Moissac »).
- **Une annonce de Nantes** (produit 394330) a des URLs d'images corrompues
  côté site (`cdn.agorastore.frproduits`, sans `/`) : sa miniature reste vide.
