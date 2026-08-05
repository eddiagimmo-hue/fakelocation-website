# Plan d'appartement — reconstruction du relevé et export AutoCAD

Reconstruit le plan à partir du croquis manuscrit (murs périphériques en rouge +
diagonales en noir) et génère les fichiers AutoCAD.

```bash
python3 plan_appartement.py
```

Aucune dépendance : Python 3 standard suffit. Trois fichiers sont produits dans
ce dossier :

| Fichier | Usage |
|---|---|
| `plan_appartement.dxf` | **Le plus simple** : `Ouvrir` directement dans AutoCAD |
| `plan_appartement.scr` | Script à jouer dans un dessin existant : ruban *Gérer > Exécuter un script* (ou commande `SCRIPT`) |
| `plan_appartement.svg` | Aperçu immédiat dans un navigateur, pour vérifier avant d'ouvrir AutoCAD |

Unité du dessin : **le centimètre** (les cotes du croquis sont reprises telles
quelles). Calques créés : `MURS` (rouge), `DIAGONALES` (gris), `COTES`, `NOMS`.

> Le `.scr` crée les textes par `entmake` (AutoLISP) : la commande `TEXT` pose un
> nombre d'invites variable selon le style courant, ce qui décalerait tout le
> script. Si votre version n'exécute pas AutoLISP, utilisez le `.dxf`.

## Comment le plan est calculé

Le relevé ne donne **aucun angle**, uniquement des longueurs : c'est une
triangulation. Les coordonnées des sommets sont donc obtenues par moindres
carrés (Levenberg–Marquardt) :

```
minimiser   Σ ( distance(Pi, Pj) − longueur_relevée )²
```

Un polygone à N sommets est entièrement défini par ses N murs **plus N−3
diagonales**. Là où le croquis n'en fournit pas assez, les décrochements
visiblement rectangulaires sont déclarés en angles droits (champ `equerre`),
traduits en diagonales de Pythagore. Ces cotes-là sont *supposées* : elles ne
sont ni tracées ni cotées dans le dessin.

Le script affiche à chaque exécution un **rapport d'écarts** cote par cote
(relevé vs. calculé). Un écart non nul signale une incohérence du relevé.

## Modifier le relevé

Tout est dans le bloc `PIECES` en haut de `plan_appartement.py` :

```python
Piece(
    nom="PIECE_1",
    pts={"A": (30, 70), ...},        # position approximative lue sur la photo
    murs=[("A", "B", 326.0), ...],   # murs rouges, dans l'ordre du contour
    diago=[("A", "F", 404.0), ...],  # diagonales noires
    equerre=["D", "E"],              # sommets supposés à 90°
    rangee=0,                        # ligne de la mise en page
)
```

`pts` sert uniquement d'amorce et à orienter la pièce comme sur le croquis :
sa précision n'a aucune influence sur le résultat. Seuls `murs`, `diago` et
`equerre` déterminent la forme.

## Ce que j'ai lu sur la photo — à contrôler

Le croquis est manuscrit et photographié : voici les points sur lesquels ma
lecture demande une confirmation.

### 1. PIECE_1 — triangle A–G–F impossible (le seul vrai conflit)

```
mur G–A (gauche)   268
mur F–G (pan coupé) 100      →  268 + 100 = 368  <  404
diagonale A–F      404
```

Un triangle dont deux côtés totalisent moins que le troisième n'existe pas. Le
solveur répartit l'écart (+12 cm sur chaque mur, −12 sur la diagonale), donc
**le pan coupé de la PIECE_1 est faux tant que cette cote n'est pas corrigée**.
Sur la photo le pan coupé est dessiné long : `100` est vraisemblablement `180`
ou `190`. À relire sur l'original.

### 2. PIECE_4 — la cote 328

Je l'ai prise comme la diagonale **A–C** (angle haut-gauche → angle bas-droit).
Lue comme D–B, elle serait impossible : `93 + 212 = 305 < 328`. Avec A–C tout
le polygone devient cohérent au centimètre près.

### 3. PIECE_3 — bande étroite

Les chiffres y sont petits et tournés. J'ai lu : murs `44 / 61 / 195 / 92 / 184`,
diagonales `202` et `158`. La cote `158` (écrite en rotation, lisible aussi
`851` ou `185`) donne un décrochement rentrant en haut de la bande. Si le mur du
haut est en réalité droit, la valeur est plutôt **185**. Les 5 côtés + 2
diagonales forment un système exactement déterminé : aucun recoupement n'est
possible, le calcul ne peut donc pas trancher à ma place.

### 4. PIECE_6 — la diagonale J–D

Lue `213`, mais le chiffre du milieu est ambigu (`213` / `223`). Les trois
angles droits du décrochement bas-droite (`33 / 114 / 30 / 29`) sont des
hypothèses de ma part, pas des mesures.

### 5. Position relative des pièces

Chaque pièce a été relevée séparément : le croquis ne donne aucune cote entre
pièces. Elles sont donc **posées côte à côte** dans l'ordre du croquis, à
assembler ensuite dans AutoCAD (les murs mitoyens évidents sont la cote `399`,
partagée entre PIECE_1 et PIECE_2, et la cote `93` entre PIECE_4 et PIECE_5).

## Surfaces obtenues

| Pièce | Sommets | Surface |
|---|---|---|
| PIECE_1 | 7 | 10,84 m² |
| PIECE_2 | 7 | 11,85 m² |
| PIECE_3 | 5 | 1,45 m² |
| PIECE_4 | 6 | 3,42 m² |
| PIECE_5 | 5 | 1,12 m² |
| PIECE_6 | 10 | 5,65 m² |

Surfaces des polygones bruts (nu intérieur relevé), hors épaisseur de cloison.
