#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconstruction du plan d'appartement a partir du releve manuel (croquis papier)
et generation des fichiers AutoCAD.

Principe
--------
Le croquis donne deux informations, et il faut les deux :

  1. des LONGUEURS  : chaque mur peripherique (rouge) et certaines diagonales
     (noir). Elles ne suffisent pas : pour figer un polygone a N sommets par
     les seules distances, il faudrait N-3 diagonales, ce que le releve ne
     fournit presque jamais.
  2. des DIRECTIONS : le trace rouge lui-meme. Un mur dessine horizontal EST
     horizontal, meme si aucune diagonale ne le dit. C'est cette information
     qui redresse le plan et lui donne l'allure du croquis.

Les coordonnees des sommets sont donc obtenues par moindres carres amortis
(Levenberg-Marquardt) sur deux familles de residus, toutes deux en centimetres :

    longueur   : ||Pi - Pj|| - longueur relevee
    direction  : deport perpendiculaire du mur par rapport a sa direction lue
                 sur le croquis (0 ou 90 degres apres equerrage, angle du
                 croquis pour les pans coupes, avec un poids plus faible)

Le residu de direction est lineaire en les coordonnees : sans echelle, il
impose l'orientation d'un mur sans rien dire de sa longueur. Les mesures
restent donc maitresses de la geometrie, le croquis de l'orientation.

Le programme affiche ensuite un RAPPORT D'ECARTS : pour chaque cote mesuree,
l'ecart entre la valeur relevee et la valeur obtenue. Un ecart important =
une cote mal relevee ou mal transcrite (voir README.md).

Sorties (dans le meme dossier) :
  * plan_appartement.scr  -> script AutoCAD (menu Gerer > Executer un script)
  * plan_appartement.dxf  -> DXF R12, ouvrable directement dans AutoCAD
  * plan_appartement.svg  -> apercu rapide dans un navigateur

Unites du dessin : centimetres (les cotes du croquis sont reprises telles quelles).

Aucune dependance externe : python3 plan_appartement.py
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. DONNEES DU RELEVE  --  c'est la seule partie a modifier
# ---------------------------------------------------------------------------
#
# Pour chaque piece :
#   pts   : sommet -> position APPROXIMATIVE lue sur le croquis, en pixels de la
#           photo (x vers la droite, y vers le BAS). Sert uniquement d'amorce au
#           calcul et a orienter la piece : la precision n'a aucune importance.
#   murs  : liste ORDONNEE des murs peripheriques (rouge), le polygone est ferme
#           automatiquement : ("A", "B", longueur)
#   diago : diagonales relevees (noir) : ("A", "F", longueur). Une longueur
#           None signale un trait present sur le croquis mais dont le chiffre
#           est illisible : il n'est ni utilise ni cote.
#   rangee : ligne de la mise en page finale (les pieces ont ete relevees
#           separement : le releve ne dit rien de leur position relative,
#           elles sont donc posees cote a cote, a assembler ensuite).
#
# Rappel : les longueurs seules ne suffisent pas (il faudrait N-3 diagonales
# par polygone). L'orientation des murs lue sur le trace rouge complete le
# systeme : voir directions_croquis().


@dataclass
class Piece:
    nom: str
    pts: dict[str, tuple[float, float]]
    murs: list[tuple[str, str, float]]
    diago: list[tuple[str, str, float | None]] = field(default_factory=list)
    rangee: int = 0

    @property
    def sommets(self) -> list[str]:
        return [a for a, _b, _l in self.murs]

    @property
    def diago_cotees(self) -> list[tuple[str, str, float]]:
        """Diagonales effectivement mesurees (celles dont le chiffre est lisible)."""
        return [(a, b, l) for a, b, l in self.diago if l is not None]

    @property
    def contraintes(self) -> list[tuple[str, str, float, str]]:
        return ([(a, b, l, "mur") for a, b, l in self.murs]
                + [(a, b, l, "diagonale") for a, b, l in self.diago_cotees])


PIECES: list[Piece] = [

    # ---------------- Croquis, rangee du haut, a gauche ---------------------
    Piece(
        nom="PIECE_1",
        pts={
            "A": (30, 70),     # angle haut-gauche
            "B": (490, 75),    # angle haut-droit
            "C": (490, 770),   # angle bas-droit
            "D": (272, 770),
            "E": (272, 685),   # decrochement
            "F": (165, 685),   # angle rentrant (station du releve)
            "G": (18, 462),    # depart du pan coupe
        },
        murs=[
            ("A", "B", 326.0),
            ("B", "C", 399.0),
            ("C", "D", 166.0),
            ("D", "E", 25.0),
            ("E", "F", 88.0),
            ("F", "G", 100.0),   # pan coupe -- cote suspecte, cf. rapport
            ("G", "A", 268.0),
        ],
        diago=[
            # Les deux diagonales aboutissent a E, l'angle SORTANT du
            # decrochement (et non a F) : A-F/B-F donnaient un triangle
            # impossible, A-E/B-E tombent a 3 et 7 cm.
            ("A", "E", 404.0),
            ("B", "E", 402.0),
        ],
        rangee=0,
    ),

    # ---------------- Croquis, rangee du haut, a droite ---------------------
    Piece(
        nom="PIECE_2",
        pts={
            "A": (550, 72),    # angle haut-gauche
            "B": (1070, 75),   # angle haut-droit
            "C": (1090, 460),  # depart du pan coupe
            "D": (975, 648),
            "E": (740, 650),   # angle rentrant (station du releve)
            "F": (740, 750),
            "G": (550, 750),   # angle bas-gauche
        },
        murs=[
            ("A", "B", 318.0),
            ("B", "C", 296.0),
            ("C", "D", 94.5),   # pan coupe
            ("D", "E", 90.0),
            ("E", "F", 36.0),
            ("F", "G", 162.0),
            ("G", "A", 399.0),
        ],
        diago=[
            ("A", "E", 398.0),
            ("B", "E", 395.0),
            ("E", "G", 163.0),
        ],
        rangee=0,
    ),

    # ---------------- Croquis, bas : bande etroite a gauche -----------------
    Piece(
        nom="PIECE_3",
        pts={
            "A": (78, 918),
            "B": (112, 888),   # petit pan coupe en haut a gauche
            "C": (215, 890),
            "D": (213, 1320),
            "E": (88, 1322),
        },
        murs=[
            ("A", "B", 44.0),
            ("B", "C", 61.0),
            ("C", "D", 195.0),
            ("D", "E", 92.0),
            ("E", "A", 184.0),
        ],
        diago=[
            ("A", "D", 202.0),
            # Deuxieme diagonale illisible sur la photo (lue 851/158/185) :
            # la geometrie des murs demande environ 197. Laissee sans valeur
            # plutot que devinee -> non utilisee, non cotee.
            ("B", "E", None),
        ],
        rangee=1,
    ),

    # ---------------- Croquis, bas : grande piece centrale ------------------
    Piece(
        nom="PIECE_4",
        pts={
            "A": (230, 870),   # angle haut-gauche
            "B": (860, 860),   # angle haut-droit
            "C": (875, 1085),  # angle bas-droit
            "D": (460, 1090),  # angle rentrant (station du releve)
            "E": (460, 1185),
            "F": (230, 1190),
        },
        murs=[
            ("A", "B", 325.0),
            ("B", "C", 93.0),
            ("C", "D", 212.0),
            ("D", "E", 14.0),
            ("E", "F", 114.0),
            ("F", "A", 110.0),
        ],
        diago=[
            ("A", "C", 328.0),   # cf. README : lue comme A-C et non D-B
            ("A", "D", 149.0),
            ("D", "F", 115.0),
        ],
        rangee=1,
    ),

    # ---------------- Croquis, bas : petite piece en haut a droite ----------
    Piece(
        nom="PIECE_5",
        # Quadrilatere : le petit cote "75" du croquis ne se place nulle part
        # (il imposerait un mur de 6 cm). Les deux traits noirs 136 et 134
        # partent du meme angle vers deux points distants de quelques cm : le
        # coin haut-droit est un angle vif, pas un pan coupe. Cf. README.
        pts={
            "A": (905, 848),    # angle haut-gauche
            "B": (1150, 838),   # angle haut-droit
            "C": (1058, 1078),  # bas du pan coupe
            "D": (905, 1078),   # angle bas-gauche (station du releve)
        },
        murs=[
            ("A", "B", 102.0),
            ("B", "C", 109.0),   # pan coupe
            ("C", "D", 37.0),
            ("D", "A", 93.0),
        ],
        diago=[
            ("D", "B", 136.0),
        ],
        rangee=1,
    ),

    # ---------------- Croquis, bas : grande piece en L ----------------------
    Piece(
        nom="PIECE_6",
        pts={
            "A": (240, 1207),
            "B": (458, 1205),
            "C": (458, 1545),
            "D": (570, 1548),
            "E": (570, 1660),
            "F": (490, 1660),
            "G": (490, 1752),
            "H": (105, 1755),
            "I": (105, 1390),
            "J": (245, 1388),   # angle rentrant (station du releve)
        },
        murs=[
            ("A", "B", 82.0),
            ("B", "C", 162.0),
            ("C", "D", 33.0),
            ("D", "E", 114.0),
            ("E", "F", 30.0),
            ("F", "G", 29.0),
            ("G", "H", 183.0),
            ("H", "I", 223.0),
            ("I", "J", 100.0),
            ("J", "A", 82.0),   # lu 48, mais la fermeture impose 82
        ],
        diago=[
            ("J", "B", 116.0),
            ("J", "F", 213.0),   # aboutit a F (211) et non a D (138)
            ("J", "G", 236.0),
            ("J", "H", 243.0),
        ],
        rangee=2,
    ),
]


# ---------------------------------------------------------------------------
# 2. SOLVEUR : moindres carres non lineaires, sans dependance
# ---------------------------------------------------------------------------

def _resoudre_systeme(A: list[list[float]], b: list[float]) -> list[float]:
    """Gauss avec pivot partiel. A est modifiee sur place."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            continue                      # direction non contrainte : dx = 0
        M[col], M[piv] = M[piv], M[col]
        inv = 1.0 / M[col][col]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] * inv
            if f:
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def _echelle_croquis(piece: Piece) -> float:
    """Rapport moyen (cote relevee / distance en pixels) pour amorcer le calcul."""
    rapports = []
    for a, b, longueur, _ in piece.contraintes:
        (xa, ya), (xb, yb) = piece.pts[a], piece.pts[b]
        d = math.hypot(xb - xa, yb - ya)
        if d > 1e-6:
            rapports.append(longueur / d)
    rapports.sort()
    return rapports[len(rapports) // 2] if rapports else 1.0


def directions_croquis(piece: Piece, tolerance_deg: float = 20.0) -> list[dict]:
    """Direction visee pour chaque mur, lue sur le trace rouge du croquis.

    C'est l'information que le croquis donne en plus des longueurs : un mur
    dessine horizontal EST horizontal, meme si aucune diagonale ne le dit. Les
    murs proches d'un axe y sont ramenes exactement (equerrage) ; les autres
    (pans coupes) gardent l'angle du croquis, mais avec un poids plus faible
    car un trait oblique a main levee est bien moins fiable qu'une equerre.
    """
    out = []
    for a, b, longueur in piece.murs:
        (xa, ya), (xb, yb) = piece.pts[a], piece.pts[b]
        angle = math.degrees(math.atan2(-(yb - ya), xb - xa))   # repere dessin
        axe = round(angle / 90.0) * 90.0
        ecart = abs((angle - axe + 180.0) % 360.0 - 180.0)
        if ecart <= tolerance_deg:
            out.append({"a": a, "b": b, "longueur": longueur,
                        "angle": axe, "axe": True})
        else:
            out.append({"a": a, "b": b, "longueur": longueur,
                        "angle": angle, "axe": False})
    return out


def resoudre(piece: Piece, poids_axe: float = 1.0, poids_oblique: float = 0.15,
             poids_ancrage: float = 0.001,
             iterations: int = 400) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """Retourne les coordonnees des sommets et le rapport d'ecarts.

    Deux familles de residus, toutes deux exprimees en centimetres :
      * longueurs  : ||Pi - Pj|| - longueur relevee ;
      * directions : ecart perpendiculaire du mur a la direction du croquis.
    Le residu de direction est lineaire en les coordonnees, donc tres stable,
    et il est sans echelle : il impose l'orientation du mur sans rien dire de
    sa longueur. C'est ce qui redresse le plan sans toucher aux mesures.
    """
    noms = piece.sommets
    idx = {nom: i for i, nom in enumerate(noms)}
    n = len(noms)

    ech = _echelle_croquis(piece)
    # y du croquis vers le bas -> y du dessin vers le haut
    ref = [(piece.pts[nom][0] * ech, -piece.pts[nom][1] * ech) for nom in noms]
    X = [list(p) for p in ref]

    contraintes = piece.contraintes
    directions = directions_croquis(piece)
    for d in directions:
        d["poids"] = poids_axe if d["axe"] else poids_oblique
        d["sin"] = math.sin(math.radians(d["angle"]))
        d["cos"] = math.cos(math.radians(d["angle"]))
    lam = 1e-3

    def ecart_direction(pos, d) -> float:
        """Deport perpendiculaire, en cm, du mur par rapport a sa direction."""
        ia, ib = idx[d["a"]], idx[d["b"]]
        return (-(pos[ib][0] - pos[ia][0]) * d["sin"]
                + (pos[ib][1] - pos[ia][1]) * d["cos"])

    def cout(pos):
        s = 0.0
        for a, b, longueur, _ in contraintes:
            ia, ib = idx[a], idx[b]
            dd = math.hypot(pos[ib][0] - pos[ia][0], pos[ib][1] - pos[ia][1])
            s += (dd - longueur) ** 2
        for d in directions:
            s += (d["poids"] * ecart_direction(pos, d)) ** 2
        for i in range(n):
            s += (poids_ancrage * (pos[i][0] - ref[i][0])) ** 2
            s += (poids_ancrage * (pos[i][1] - ref[i][1])) ** 2
        return s

    cout_courant = cout(X)

    for _ in range(iterations):
        # Equations normales J^T J dx = -J^T r, construites directement
        m = 2 * n
        JtJ = [[0.0] * m for _ in range(m)]
        Jtr = [0.0] * m

        def accumuler(g, r):
            for k, gk in g:
                Jtr[k] += gk * r
                for l, gl in g:
                    JtJ[k][l] += gk * gl

        for a, b, longueur, _ in contraintes:
            ia, ib = idx[a], idx[b]
            dx = X[ib][0] - X[ia][0]
            dy = X[ib][1] - X[ia][1]
            d = math.hypot(dx, dy)
            if d < 1e-9:
                dx, dy, d = 1e-6, 0.0, 1e-6
            ux, uy = dx / d, dy / d
            # d(residu)/d(coord) : -u sur le sommet a, +u sur le sommet b
            accumuler([(2 * ia, -ux), (2 * ia + 1, -uy),
                       (2 * ib, ux), (2 * ib + 1, uy)], d - longueur)

        for d in directions:
            ia, ib = idx[d["a"]], idx[d["b"]]
            w, si, co = d["poids"], d["sin"], d["cos"]
            accumuler([(2 * ia, w * si), (2 * ia + 1, -w * co),
                       (2 * ib, -w * si), (2 * ib + 1, w * co)],
                      w * ecart_direction(X, d))

        for i in range(n):
            for k, (xi, xr) in enumerate(((X[i][0], ref[i][0]), (X[i][1], ref[i][1]))):
                j = 2 * i + k
                JtJ[j][j] += poids_ancrage ** 2
                Jtr[j] += poids_ancrage ** 2 * (xi - xr)

        # Amortissement de Levenberg-Marquardt
        for j in range(m):
            JtJ[j][j] += lam * max(JtJ[j][j], 1e-9) + 1e-9

        dX = _resoudre_systeme(JtJ, [-v for v in Jtr])
        essai = [[X[i][0] + dX[2 * i], X[i][1] + dX[2 * i + 1]] for i in range(n)]
        cout_essai = cout(essai)

        if cout_essai < cout_courant:
            pas = max(abs(v) for v in dX) if dX else 0.0
            X, cout_courant = essai, cout_essai
            lam = max(lam * 0.4, 1e-9)
            if pas < 1e-9:
                break
        else:
            lam *= 4.0
            if lam > 1e12:
                break

    coords = {nom: (X[i][0], X[i][1]) for nom, i in idx.items()}
    rapport = []
    for a, b, longueur, genre in contraintes:
        (xa, ya), (xb, yb) = coords[a], coords[b]
        obtenu = math.hypot(xb - xa, yb - ya)
        rapport.append({"a": a, "b": b, "genre": genre,
                        "releve": longueur, "obtenu": obtenu,
                        "ecart": obtenu - longueur})

    # Ecart angulaire final de chaque mur par rapport au croquis
    angles = []
    for d in directions:
        (xa, ya), (xb, yb) = coords[d["a"]], coords[d["b"]]
        obtenu = math.degrees(math.atan2(yb - ya, xb - xa))
        ecart = (obtenu - d["angle"] + 180.0) % 360.0 - 180.0
        angles.append({"a": d["a"], "b": d["b"], "axe": d["axe"],
                       "vise": d["angle"], "ecart": ecart})
    return coords, {"cotes": rapport, "angles": angles}


def disposer(pieces_resolues: dict[str, dict[str, tuple[float, float]]],
             ecart: float = 150.0) -> None:
    """Range les pieces en rangees sans chevauchement.

    Le releve mesure chaque piece separement : il ne dit rien de leur position
    les unes par rapport aux autres. On les pose donc cote a cote, dans l'ordre
    du croquis ; l'assemblage final se fait ensuite dans AutoCAD.
    """
    def bbox(c):
        xs = [p[0] for p in c.values()]
        ys = [p[1] for p in c.values()]
        return min(xs), min(ys), max(xs), max(ys)

    y_haut = 0.0
    for rangee in sorted({p.rangee for p in PIECES}):
        de_la_rangee = [p for p in PIECES if p.rangee == rangee]
        hauteur = max(bbox(pieces_resolues[p.nom])[3] - bbox(pieces_resolues[p.nom])[1]
                      for p in de_la_rangee)
        x_gauche = 0.0
        for p in de_la_rangee:
            c = pieces_resolues[p.nom]
            x0, y0, x1, _y1 = bbox(c)
            dx, dy = x_gauche - x0, (y_haut - hauteur) - y0
            for k in c:
                c[k] = (c[k][0] + dx, c[k][1] + dy)
            x_gauche += (x1 - x0) + ecart
        y_haut -= hauteur + ecart


# ---------------------------------------------------------------------------
# 3. SORTIE AUTOCAD (.scr)
# ---------------------------------------------------------------------------

CALQUES = [("MURS", 1), ("DIAGONALES", 8), ("COTES", 3), ("NOMS", 4)]
H_COTE = 12.0     # hauteur du texte des cotes, en unites dessin
H_NOM = 25.0      # hauteur du texte des noms de piece


def _n(v: float) -> str:
    return f"{v:.3f}"


def _milieu(p, q):
    return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)


def _pose_nom(coords, sommets) -> tuple[tuple[float, float], float]:
    """Nom de la piece juste au-dessus du polygone, pour ne masquer aucune cote."""
    xs = [coords[s][0] for s in sommets]
    ys = [coords[s][1] for s in sommets]
    hauteur = max(12.0, min(H_NOM, (max(xs) - min(xs)) / 6.0))
    return ((min(xs) + max(xs)) / 2.0, max(ys) + hauteur), hauteur


def _angle_texte(p, q) -> float:
    """Angle en degres, toujours lisible (jamais a l'envers)."""
    a = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
    if a > 90:
        a -= 180
    elif a <= -90:
        a += 180
    return a


def _texte_lisp(calque: str, p, hauteur: float, angle_deg: float, contenu: str) -> str:
    """Texte centre, cree par entmake.

    On n'utilise pas la commande TEXT : le nombre de questions posees depend du
    style courant (une hauteur figee dans le style supprime une invite et
    decale tout le reste du script). entmake, lui, est deterministe.
    """
    pt = f"(list {p[0]:.3f} {p[1]:.3f} 0.0)"
    contenu = contenu.replace("\\", "\\\\").replace('"', '\\"')
    return ("(progn (entmake (list '(0 . \"TEXT\") (cons 8 \"%s\") "
            "(cons 10 %s) (cons 11 %s) (cons 40 %.3f) (cons 50 %.6f) "
            "'(72 . 1) '(73 . 2) (cons 1 \"%s\"))) (princ))"
            % (calque, pt, pt, hauteur, math.radians(angle_deg), contenu))


def ecrire_scr(chemin: str, solutions: dict[str, dict[str, tuple[float, float]]]) -> None:
    L: list[str] = []
    # Commandes prefixees par _ et . : fonctionne aussi sur AutoCAD francais
    L += ["CMDECHO", "0", "OSMODE", "0", "BLIPMODE", "0"]
    L += ["_.UNDO", "_BEgin"]

    L.append("_.-LAYER")
    for nom, couleur in CALQUES:
        L += ["_Make", nom, "_Color", str(couleur), ""]
    L.append("")

    for piece in PIECES:
        coords = solutions[piece.nom]

        L += [f"(princ \"\\nTrace {piece.nom}\")(princ)"]

        # --- murs peripheriques : une polyligne fermee
        L += ["CLAYER", "MURS", "_.PLINE"]
        L += [f"{_n(coords[s][0])},{_n(coords[s][1])}" for s in piece.sommets]
        L += ["_Close"]

        # --- diagonales de controle
        if piece.diago_cotees:
            L.append("CLAYER")
            L.append("DIAGONALES")
            for a, b, _l in piece.diago_cotees:
                L += ["_.LINE",
                      f"{_n(coords[a][0])},{_n(coords[a][1])}",
                      f"{_n(coords[b][0])},{_n(coords[b][1])}",
                      ""]

        # --- cotes (texte au milieu de chaque segment)
        for a, b, longueur in piece.murs + piece.diago_cotees:
            L.append(_texte_lisp("COTES", _milieu(coords[a], coords[b]), H_COTE,
                                 _angle_texte(coords[a], coords[b]), f"{longueur:g}"))

        # --- nom de la piece au centre
        pos, h = _pose_nom(coords, piece.sommets)
        L.append(_texte_lisp("NOMS", pos, h, 0.0, piece.nom))

    L += ["CLAYER", "MURS", "_.ZOOM", "_Extents", "_.UNDO", "_End", "CMDECHO", "1"]

    # Un script AutoCAD lit une ligne = une saisie ; il doit finir par un saut
    with open(chemin, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------------------
# 4. SORTIE DXF R12 (ouverture directe dans AutoCAD)
# ---------------------------------------------------------------------------

def ecrire_dxf(chemin: str, solutions: dict[str, dict[str, tuple[float, float]]]) -> None:
    out: list[str] = []

    def g(code: int, valeur) -> None:
        out.append(str(code))
        out.append(f"{valeur:.4f}" if isinstance(valeur, float) else str(valeur))

    xs = [p[0] for c in solutions.values() for p in c.values()]
    ys = [p[1] for c in solutions.values() for p in c.values()]

    # --- En-tete : sans lui, AutoCAD ouvre le fichier sans etendues ni unites
    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$INSBASE"); g(10, 0.0); g(20, 0.0); g(30, 0.0)
    g(9, "$EXTMIN"); g(10, min(xs)); g(20, min(ys)); g(30, 0.0)
    g(9, "$EXTMAX"); g(10, max(xs)); g(20, max(ys)); g(30, 0.0)
    g(9, "$LIMMIN"); g(10, min(xs)); g(20, min(ys))
    g(9, "$LIMMAX"); g(10, max(xs)); g(20, max(ys))
    g(9, "$INSUNITS"); g(70, 5)               # 5 = centimetres
    g(9, "$LUNITS"); g(70, 2)                 # unites decimales
    g(9, "$TEXTSTYLE"); g(7, "STANDARD")
    g(0, "ENDSEC")

    g(0, "SECTION"); g(2, "TABLES")

    g(0, "TABLE"); g(2, "LTYPE"); g(70, 1)
    g(0, "LTYPE"); g(2, "CONTINUOUS"); g(70, 0); g(3, "Solid line")
    g(72, 65); g(73, 0); g(40, 0.0)
    g(0, "ENDTAB")

    g(0, "TABLE"); g(2, "STYLE"); g(70, 1)
    g(0, "STYLE"); g(2, "STANDARD"); g(70, 0); g(40, 0.0); g(41, 1.0)
    g(50, 0.0); g(71, 0); g(42, 2.5); g(3, "txt"); g(4, "")
    g(0, "ENDTAB")

    g(0, "TABLE"); g(2, "LAYER"); g(70, len(CALQUES) + 1)
    g(0, "LAYER"); g(2, "0"); g(70, 0); g(62, 7); g(6, "CONTINUOUS")
    for nom, couleur in CALQUES:
        g(0, "LAYER"); g(2, nom); g(70, 0); g(62, couleur); g(6, "CONTINUOUS")
    g(0, "ENDTAB")

    g(0, "ENDSEC")

    g(0, "SECTION"); g(2, "ENTITIES")

    def polyligne_fermee(calque, points):
        """POLYLINE R12 : un seul objet manipulable (deplacer, decaler, surface)."""
        g(0, "POLYLINE"); g(8, calque); g(66, 1); g(70, 1)   # 70 = 1 : fermee
        g(10, 0.0); g(20, 0.0); g(30, 0.0)
        for p in points:
            g(0, "VERTEX"); g(8, calque)
            g(10, float(p[0])); g(20, float(p[1])); g(30, 0.0)
        g(0, "SEQEND"); g(8, calque)

    def ligne(calque, p, q):
        g(0, "LINE"); g(8, calque)
        g(10, float(p[0])); g(20, float(p[1])); g(30, 0.0)
        g(11, float(q[0])); g(21, float(q[1])); g(31, 0.0)

    def texte(calque, p, hauteur, angle, contenu):
        g(0, "TEXT"); g(8, calque)
        g(10, float(p[0])); g(20, float(p[1])); g(30, 0.0)
        g(40, float(hauteur)); g(1, contenu); g(50, float(angle))
        g(7, "STANDARD")
        g(72, 1); g(73, 2)                       # justification centre / milieu
        g(11, float(p[0])); g(21, float(p[1])); g(31, 0.0)

    for piece in PIECES:
        coords = solutions[piece.nom]
        sommets = piece.sommets
        polyligne_fermee("MURS", [coords[s] for s in sommets])
        for a, b, _l in piece.diago_cotees:
            ligne("DIAGONALES", coords[a], coords[b])
        for a, b, longueur in piece.murs + piece.diago_cotees:
            texte("COTES", _milieu(coords[a], coords[b]), H_COTE,
                  _angle_texte(coords[a], coords[b]), f"{longueur:g}")
        pos, h = _pose_nom(coords, sommets)
        texte("NOMS", pos, h, 0.0, piece.nom)

    g(0, "ENDSEC"); g(0, "EOF")

    with open(chemin, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# 5. APERCU SVG
# ---------------------------------------------------------------------------

def ecrire_svg(chemin: str, solutions: dict[str, dict[str, tuple[float, float]]]) -> None:
    xs = [p[0] for c in solutions.values() for p in c.values()]
    ys = [p[1] for c in solutions.values() for p in c.values()]
    marge = 60.0
    x0, x1 = min(xs) - marge, max(xs) + marge
    y0, y1 = min(ys) - marge, max(ys) + marge
    larg, haut = x1 - x0, y1 - y0

    def T(p):  # repere dessin -> repere SVG (y inverse)
        return (p[0] - x0, y1 - p[1])

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larg:.1f} {haut:.1f}" '
         f'width="1100" font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{larg:.1f}" height="{haut:.1f}" fill="#fbfaf8"/>']

    for piece in PIECES:
        coords = solutions[piece.nom]
        pts = " ".join(f"{T(coords[s])[0]:.2f},{T(coords[s])[1]:.2f}"
                       for s in piece.sommets)
        s.append(f'<polygon points="{pts}" fill="#e8434322" stroke="#e04030" '
                 f'stroke-width="6" stroke-linejoin="round"/>')
        for a, b, _l in piece.diago_cotees:
            pa, pb = T(coords[a]), T(coords[b])
            s.append(f'<line x1="{pa[0]:.2f}" y1="{pa[1]:.2f}" x2="{pb[0]:.2f}" '
                     f'y2="{pb[1]:.2f}" stroke="#8898a8" stroke-width="1.6"/>')
        for a, b, longueur in piece.murs + piece.diago_cotees:
            mx, my = T(_milieu(coords[a], coords[b]))
            ang = -_angle_texte(coords[a], coords[b])
            s.append(f'<text x="{mx:.2f}" y="{my:.2f}" font-size="15" fill="#222" '
                     f'text-anchor="middle" dominant-baseline="middle" '
                     f'transform="rotate({ang:.1f} {mx:.2f} {my:.2f})">{longueur:g}</text>')
        pos, h = _pose_nom(coords, piece.sommets)
        nx, ny = T(pos)
        s.append(f'<text x="{nx:.2f}" y="{ny:.2f}" font-size="{max(h, 18):.0f}" '
                 f'fill="#8a2a20" text-anchor="middle" opacity="0.8">{piece.nom}</text>')

    s.append('</svg>')
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(s))


# ---------------------------------------------------------------------------
# 6. PROGRAMME PRINCIPAL
# ---------------------------------------------------------------------------

def main() -> None:
    dossier = os.path.dirname(os.path.abspath(__file__))
    solutions: dict[str, dict[str, tuple[float, float]]] = {}
    rapports: dict[str, list[dict]] = {}

    for piece in PIECES:
        coords, rapport = resoudre(piece)
        solutions[piece.nom] = coords
        rapports[piece.nom] = rapport

    disposer(solutions)

    print("RAPPORT DE COHERENCE DU RELEVE")
    print("=" * 66)
    suspects: list[str] = []
    for piece in PIECES:
        n = len(piece.sommets)
        aire = 0.0
        c = solutions[piece.nom]
        som = piece.sommets
        for i, s in enumerate(som):
            p, q = c[s], c[som[(i + 1) % n]]
            aire += p[0] * q[1] - q[0] * p[1]
        aire = abs(aire) / 2.0

        print(f"\n{piece.nom} : {n} sommets, surface {aire / 10000:.2f} m2")
        for a, b, l in piece.diago:
            if l is None:
                print(f"  {a}-{b:<2} diagonale tracee sur le croquis mais cote illisible "
                      f": non utilisee")
        for r in rapports[piece.nom]["cotes"]:
            drapeau = ""
            if abs(r["ecart"]) > 3.0:
                drapeau = "   <<< A VERIFIER"
                suspects.append(f"{piece.nom} {r['a']}-{r['b']} "
                                f"({r['genre']} {r['releve']:g})")
            print(f"  {r['a']}-{r['b']:<2} {r['genre']:<10} releve {r['releve']:>7.1f} "
                  f"  calcule {r['obtenu']:>7.1f}   ecart {r['ecart']:+6.1f}{drapeau}")

        devies = [a for a in rapports[piece.nom]["angles"]
                  if a["axe"] and abs(a["ecart"]) > 1.5]
        if devies:
            for a in devies:
                print(f"  {a['a']}-{a['b']:<2} mur dessine "
                      f"{'horizontal' if a['vise'] % 180 == 0 else 'vertical':<10} "
                      f"mais devie de {a['ecart']:+5.1f} deg pour respecter les cotes")

    print("\n" + "=" * 66)
    if suspects:
        print("Cotes a recontroler sur le croquis :")
        for s in suspects:
            print("  - " + s)
    else:
        print("Toutes les cotes sont coherentes (ecart < 3 cm).")

    scr = os.path.join(dossier, "plan_appartement.scr")
    dxf = os.path.join(dossier, "plan_appartement.dxf")
    svg = os.path.join(dossier, "plan_appartement.svg")
    ecrire_scr(scr, solutions)
    ecrire_dxf(dxf, solutions)
    ecrire_svg(svg, solutions)
    print("\nFichiers generes :")
    for f in (scr, dxf, svg):
        print("  " + f)


if __name__ == "__main__":
    main()
