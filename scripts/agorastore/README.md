# Veille Agorastore-Immo — ventes terminées sans aucune enchère

Produit `annonces_sans_enchere_agorastore.xlsx` : toutes les ventes immobilières
terminées sur [agorastore-immo.fr](https://www.agorastore-immo.fr) depuis le
1<sup>er</sup> janvier 2023 qui n'ont reçu **aucune enchère**.

## Lancer

```bash
./run_all.sh
```

Les dépendances (`requests`, `openpyxl`, `Pillow`) sont installées au besoin.
Le proxy HTTPS est lu depuis `$HTTPS_PROXY` — rien à modifier quand son port
change d'une session à l'autre.

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
| `scrape.py` | parcourt les 6 catégories immobilières, retient `totalBids == 0` et `saleStatus == 2` (terminée) |
| `enrich.py` | ouvre chaque fiche produit : prix de mise à prix, ville, re-vérification du nombre d'enchères |
| `dedup.py` | un bien listé dans deux catégories ne doit produire qu'une ligne |
| `add_postal.py` | code postal + ville normalisée |
| `get_population.py` | population de la commune |
| `get_surfaces.py` | surface bâtie et surface de parcelle |
| `get_images.py` | télécharge et réduit les miniatures |
| `make_xlsx.py` | assemble le classeur |

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
