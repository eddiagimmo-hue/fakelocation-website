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

Le croquis donne **deux** informations, et il faut les deux :

1. **Les longueurs** — murs et diagonales. Elles ne suffisent pas : pour figer
   un polygone à N sommets par les seules distances, il faudrait N−3 diagonales,
   ce que le relevé ne fournit presque jamais.
2. **Les directions** — le tracé rouge lui-même. Un mur dessiné horizontal *est*
   horizontal, même si aucune diagonale ne le dit. C'est cette information qui
   redresse le plan.

Les coordonnées des sommets sont donc obtenues par moindres carrés amortis
(Levenberg–Marquardt) sur deux familles de résidus, toutes deux en centimètres :

```
longueur    ‖Pi − Pj‖ − longueur relevée
direction   déport perpendiculaire du mur par rapport à sa direction du croquis
```

Les murs à moins de 20° d'un axe sont ramenés exactement à l'horizontale ou à la
verticale (équerrage) ; les pans coupés gardent l'angle du croquis avec un poids
plus faible, un trait oblique à main levée étant moins fiable qu'une équerre.
Le résidu de direction est linéaire en les coordonnées : sans échelle, il impose
l'orientation d'un mur sans rien dire de sa longueur. **Les mesures restent
maîtresses de la géométrie, le croquis de l'orientation.**

Le script affiche à chaque exécution un **rapport d'écarts** cote par cote
(relevé vs. calculé), plus les murs qui ont dû s'écarter de leur axe.

## Modifier le relevé

Tout est dans le bloc `PIECES` en haut de `plan_appartement.py` :

```python
Piece(
    nom="PIECE_1",
    pts={"A": (30, 70), ...},        # position approximative lue sur la photo
    murs=[("A", "B", 326.0), ...],   # murs rouges, dans l'ordre du contour
    diago=[("A", "E", 404.0), ...],  # diagonales noires (None = cote illisible)
    rangee=0,                        # ligne de la mise en page
)
```

`pts` sert à deux choses : amorcer le calcul, et **donner la direction de chaque
mur**. Sa précision en longueur n'a aucune importance (le croquis n'est pas à
l'échelle), mais l'orientation de chaque segment compte : c'est elle qui décide
si un mur est horizontal, vertical ou oblique.

## Corrections de lecture apportées au croquis

Trois de mes transcriptions initiales étaient géométriquement impossibles. Dans
chaque cas la correction n'est pas une supposition : elle est imposée par les
autres mesures. À confirmer sur l'original.

### PIECE_6 — le mur `J–A` vaut 82 et non 48

Les 10 murs sont tous d'équerre. En horizontal ils se ferment à 2 cm près
(82 + 33 − 30 − 183 + 100), mais en vertical il manquait 34 cm. Avec `J–A = 82`
la fermeture est exacte, **et** les trois diagonales tombent d'un coup :

| diagonale | relevé | calculé |
|---|---|---|
| J–B | 116 | 115 |
| J–G | 236 | 238 |
| J–H | 243 | 244 |

### PIECE_6 — la 4ᵉ diagonale aboutit à `F`, pas à `D`

`J–D` mesure 138 dans la pièce fermée, `J–F` mesure 211. La cote relevée est
213 : c'est `J–F`.

### PIECE_1 — les deux diagonales aboutissent à `E`, pas à `F`

`E` est l'angle **sortant** du décrochement, `F` l'angle rentrant. Lues sur `F`,
elles donnaient un triangle impossible (`268 + 100 = 368 < 404`). Lues sur `E`,
tout rentre dans l'ordre : `B–E` tombe à 2 cm, `A–E` à 6 cm.

### PIECE_5 — le petit côté `75` ne se place nulle part

Pour respecter les autres cotes il faudrait un mur de 6 cm : l'angle haut-droit
est donc un angle vif, pas un pan coupé, et la pièce est un quadrilatère. Les
deux traits noirs `136` et `134` partent du même angle vers deux points distants
de quelques centimètres, ce qui confirme cette lecture. Seul `136` est retenu
(il tombe à 2 mm) ; `75` et `134` ne sont pas utilisés. **C'est le point le plus
incertain du relevé** — à revoir sur l'original.

### PIECE_3 — deuxième diagonale illisible

Lisible `851`, `158` ou `185` selon l'orientation. La géométrie des murs demande
environ 197. Plutôt que de deviner, elle est déclarée `None` : ni utilisée, ni
cotée. Le reste de la pièce tombe à 2,3 cm près sans elle.

## Ce qui reste à vérifier

Après correction, deux pièces gardent une tension :

- **PIECE_1**, le pan coupé `F–G` relevé `100` veut faire 107, et le mur
  `G–A` relevé `268` veut faire 273. La pièce est cohérente à ~6 cm, mais ce
  coin mérite un coup de mètre.
- **PIECE_4**, la diagonale `328` veut faire 334 (je l'ai lue `A–C`). La pièce
  est de toute façon surdéterminée : ses murs se ferment seuls à 3 cm près.

Toutes les autres cotes tombent à moins de 2,5 cm.

## Position relative des pièces

Chaque pièce a été relevée séparément : le croquis ne donne aucune cote entre
pièces. Elles sont donc **posées côte à côte** dans l'ordre du croquis, à
assembler ensuite dans AutoCAD (les murs mitoyens évidents sont la cote `399`,
partagée entre PIECE_1 et PIECE_2, et la cote `93` entre PIECE_4 et PIECE_5).

## Surfaces obtenues

| Pièce | Sommets | Surface |
|---|---|---|
| PIECE_1 | 7 | 11,95 m² |
| PIECE_2 | 7 | 11,87 m² |
| PIECE_3 | 5 | 1,85 m² |
| PIECE_4 | 6 | 3,21 m² |
| PIECE_5 | 4 | 0,64 m² |
| PIECE_6 | 10 | 5,08 m² |

Surfaces des polygones bruts (nu intérieur relevé), hors épaisseur de cloison.
