# releve2plan — d'un relevé au mètre vers un plan AutoCAD

Reconstruit un plan à partir d'un relevé de terrain par triangulation (murs
périphériques + diagonales) et l'exporte vers AutoCAD.

```bash
python3 releve2plan.py plan_appartement.releve
```

Aucune dépendance : Python 3.9+ suffit. Trois fichiers sont produits à côté du
relevé, sous le même nom de base :

| Fichier | Usage |
|---|---|
| `.dxf` | **Le plus simple** : `Ouvrir` directement dans AutoCAD |
| `.scr` | Script à jouer dans un dessin existant : *Gérer > Exécuter un script* |
| `.svg` | Aperçu immédiat dans un navigateur, pour vérifier avant AutoCAD |

Options : `-o DOSSIER` (dossier de sortie), `--prefixe NOM` (nom des fichiers),
`--tolerance T` (seuil de signalement, 3 par défaut), `--poids-axe P`
(force de l'équerrage, voir plus bas).

Ce dossier contient aussi `plan_appartement.releve`, un relevé complet de six
pièces qui sert d'exemple.

## Le fichier de relevé

Un fichier texte. Les lignes vides et tout ce qui suit un `#` sont ignorés. Le
point ou la virgule décimale, indifféremment.

```
PIECE Séjour
    MUR  326  E          # 326 cm vers l'est (la droite)
    MUR  399  S
    MUR  166  O
    MUR   25  N
    MUR   88  O
    MUR  100  NO         # pan coupé : direction approximative
    MUR  268  N          # le polygone se referme tout seul
    DIAG A E 404         # diagonale entre les sommets A et E
    DIAG B E 402
    RANGEE 0             # facultatif : ligne de la mise en page
```

**Les sommets sont nommés tout seuls** dans l'ordre des murs : `A` est le point
de départ, `B` la fin du premier mur, `C` la fin du deuxième… Le dernier mur
revient sur `A`. Le rapport et le dessin utilisent ces mêmes lettres : pour
noter une diagonale, il suffit donc de compter les murs sur le croquis.

Directions admises :

| Notation | Effet |
|---|---|
| `E` `N` `O` `S` (ou `W`) | mur mis **exactement** d'équerre |
| `NE` `NO` `SE` `SO` (ou `NW`, `SW`) | direction indicative |
| `145` — un angle en degrés | direction indicative (0 = est, sens trigo) |

Seules les cardinales sont mises d'équerre : un trait oblique à main levée vaut
bien moins qu'une équerre, il est donc pris avec un poids plus faible et c'est
la mesure qui tranche.

Une diagonale tracée sur le croquis mais dont le chiffre est illisible se note
`DIAG B E ?` : elle est signalée, mais ni utilisée ni cotée.

## Pourquoi les directions

Un relevé au mètre donne des longueurs et **aucun angle**. Ça ne suffit pas :
pour figer un polygone à N sommets par les seules distances, il faudrait N−3
diagonales, ce qu'on ne relève quasiment jamais. Sans information
supplémentaire, les pièces sortent de biais.

L'information manquante est sur le croquis, sous les yeux : la direction de
chaque mur. Un mur dessiné horizontal *est* horizontal. C'est gratuit à noter
et ça redresse tout le plan.

Les coordonnées sont donc obtenues par moindres carrés amortis
(Levenberg–Marquardt) sur deux familles de résidus, toutes deux dans l'unité du
relevé :

```
longueur    ‖Pi − Pj‖ − longueur relevée
direction   déport perpendiculaire du mur par rapport à sa direction
```

Le résidu de direction est linéaire en les coordonnées et sans échelle : il
oriente le mur sans rien dire de sa longueur. **Les mesures restent maîtresses
de la géométrie, le croquis de l'orientation.** `--poids-axe 0` désactive
entièrement les directions et ne garde que les mesures.

## Le diagnostic

Sur un relevé manuscrit, l'erreur habituelle n'est pas la mesure : c'est la
transcription — un chiffre mal lu, une diagonale rattachée au mauvais angle. Le
programme reconstruit donc chaque pièce **sans ses diagonales**, à partir des
seuls murs et de leurs directions, puis :

- regarde de combien la pièce ne se referme pas, et propose la cote de mur qui
  la refermerait ;
- si un seul mur est oblique, en déduit sa longueur et son angle réels ;
- confronte chaque diagonale relevée à toutes les paires de sommets, et signale
  quand une autre paire correspond nettement mieux.

Exemple réel, sur la transcription initiale de ce relevé :

```
PIECE_6 :
  - le contour ne se referme pas : +2.0 en horizontal, -34.0 en vertical.
     le mur B-C a 162 refermerait la piece a 128
     le mur D-E a 114 refermerait la piece a 80
     le mur H-I a 223 refermerait la piece a 257
     le mur J-A a 48 refermerait la piece a 82
```

`J-A = 82` était la bonne réponse. Le programme ne tranche pas à votre place —
il réduit la recherche à quatre candidats au lieu de dix murs.

**Procédez en deux temps.** Tant que le contour ne se referme pas, le squelette
est faux et les distances calculées avec : le programme le dit et s'abstient de
proposer un rattachement de diagonale. Corrigez d'abord la fermeture, relancez,
et les diagonales deviennent lisibles :

```
PIECE_6 :
  - la diagonale J-D relevee a 213 mesure 139 : elle correspond plutot a F-J (211).
```

## Le DXF produit

R12 (`AC1009`), lu par toutes les versions d'AutoCAD et par les autres logiciels
de CAO. Unité déclarée en centimètres (`$INSUNITS` = 5). Calques `MURS` (rouge),
`DIAGONALES` (gris), `COTES`, `NOMS`.

Chaque pièce est une **polyligne fermée** : elle se déplace d'un bloc, se décale
(`DECALER`) pour donner l'épaisseur des cloisons, et sa surface se lit avec
`AIRE > Objet`. Les diagonales sont des lignes séparées sur leur propre calque,
à geler une fois le plan contrôlé. La hauteur des textes s'adapte à la taille du
relevé.

> Le `.scr` crée ses textes par `entmake` (AutoLISP) : la commande `TEXT` pose un
> nombre d'invites variable selon le style courant, ce qui décalerait tout le
> script. Si votre version n'exécute pas AutoLISP, utilisez le `.dxf`.

## Limites

- **Les pièces doivent être croquées à peu près droites.** L'équerrage ne
  s'applique qu'aux murs déclarés cardinaux. Une pièce entièrement oblique
  repasserait en directions indicatives, à poids faible.
- **Le relevé ne dit rien de la position des pièces entre elles**, chacune ayant
  été mesurée séparément. Elles sont posées côte à côte, par rangées de trois
  par défaut (`RANGEE n` pour choisir) ; l'assemblage se fait dans AutoCAD.
- Le diagnostic propose, il ne décide pas. Une pièce sur-déterminée par ses
  mesures peut rester en tension sans qu'aucun coupable ne se dégage.

## Le relevé d'exemple

`plan_appartement.releve` : six pièces. Après correction, tous les écarts
tombent sous 2,5 cm sauf le pan coupé de la PIECE_1, signalé par le diagnostic
(`100` relevé, 128 nécessaire pour fermer).

| Pièce | Sommets | Surface |
|---|---|---|
| PIECE_1 | 7 | 11,96 m² |
| PIECE_2 | 7 | 11,88 m² |
| PIECE_3 | 5 | 1,85 m² |
| PIECE_4 | 6 | 3,22 m² |
| PIECE_5 | 4 | 0,63 m² |
| PIECE_6 | 10 | 5,08 m² |

Surfaces des polygones bruts (nu intérieur relevé), hors épaisseur de cloison.

Quatre transcriptions initiales étaient impossibles ; les trois premières sont
retrouvées par le diagnostic, la quatrième a été confirmée par le releveur :

| Pièce | Lu | Corrigé | Comment |
|---|---|---|---|
| PIECE_6 | mur `48` | `82` | imposé par la fermeture, confirmé par 3 diagonales |
| PIECE_6 | `DIAG J D 213` | `DIAG J F 213` | `J–D` mesure 138, `J–F` mesure 211 |
| PIECE_1 | `DIAG A F` / `B F` | `DIAG A E` / `B E` | sur `F` : `268 + 100 = 368 < 404`, impossible |
| PIECE_4 | `328` | `228` sur `B–D` | erreur d'écriture confirmée par le releveur |

La PIECE_5 reste le point le plus incertain : le côté `75` du croquis ne se
place nulle part (il imposerait un mur de 6 cm), la pièce est traitée en
quadrilatère à angle vif et les cotes `75` et `134` ne sont pas utilisées.
