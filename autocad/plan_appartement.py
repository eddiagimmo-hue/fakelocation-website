#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconstruction du plan d'appartement a partir du releve manuel (croquis papier)
et generation des fichiers AutoCAD.

Principe
--------
Chaque piece est un polygone ferme dont on connait :
  * la longueur de chaque mur peripherique (traits rouges du croquis)
  * la longueur de certaines diagonales (traits noirs du croquis)
  * eventuellement, les decrochements visiblement rectangulaires, declares en
    angles droits la ou le croquis ne fournit pas assez de diagonales

Le releve est donc une TRIANGULATION : on ne connait aucun angle, seulement des
longueurs. On retrouve les coordonnees des sommets par moindres carres
(Gauss-Newton amorti / Levenberg-Marquardt) :

    minimiser  sum_k ( ||Pi - Pj|| - L_k )^2  +  w * sum_v ||Pv - Pv_croquis||^2

Le second terme (poids w tres faible) sert a donner une forme raisonnable aux
rares degres de liberte non contraints quand il manque une diagonale. La
solution est ensuite remise droite par recalage rigide sur le croquis
(fonction orienter), les longueurs seules ne fixant ni la rotation ni le sens
de parcours.

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
#   diago : diagonales relevees (noir) : ("A", "F", longueur)
#   equerre : sommets ou l'angle est suppose DROIT (decrochements, retours de
#           cloison). Le croquis ne donne pas de diagonale a ces endroits, mais
#           un decrochement rectangulaire se lit sans ambiguite sur le dessin.
#           Chaque angle droit remplace exactement une diagonale manquante :
#           il est traduit en pseudo-diagonale de Pythagore entre les deux
#           sommets voisins.
#   rangee : ligne de la mise en page finale (les pieces ont ete relevees
#           separement : le releve ne dit rien de leur position relative,
#           elles sont donc posees cote a cote, a assembler ensuite).
#
# Rappel : un polygone a N sommets est entierement defini par ses N murs plus
# N-3 diagonales (angles droits compris). Moins => la forme reste partiellement
# libre : le solveur garde l'allure du croquis et le signale.


@dataclass
class Piece:
    nom: str
    pts: dict[str, tuple[float, float]]
    murs: list[tuple[str, str, float]]
    diago: list[tuple[str, str, float]] = field(default_factory=list)
    equerre: list[str] = field(default_factory=list)
    rangee: int = 0

    @property
    def sommets(self) -> list[str]:
        return [a for a, _b, _l in self.murs]

    @property
    def equerres(self) -> list[tuple[str, str, float]]:
        """Angles droits traduits en distances entre sommets voisins."""
        som = self.sommets
        longueurs = {(a, b): l for a, b, l in self.murs}
        out = []
        for nom in self.equerre:
            i = som.index(nom)
            avant, apres = som[i - 1], som[(i + 1) % len(som)]
            la = longueurs[(avant, nom)]
            lb = longueurs[(nom, apres)]
            out.append((avant, apres, math.hypot(la, lb)))
        return out

    @property
    def contraintes(self) -> list[tuple[str, str, float, str]]:
        return ([(a, b, l, "mur") for a, b, l in self.murs]
                + [(a, b, l, "diagonale") for a, b, l in self.diago]
                + [(a, b, l, "equerre") for a, b, l in self.equerres])


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
            ("A", "F", 404.0),
            ("B", "F", 402.0),
        ],
        equerre=["D", "E"],   # decrochement 166 / 25 / 88 : angles droits
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
        equerre=["B"],        # mur de droite perpendiculaire au mur du haut
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
            ("B", "E", 158.0),   # lecture incertaine sur la photo
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
        pts={
            "A": (905, 848),
            "B": (1150, 838),
            "C": (1165, 880),
            "D": (1058, 1078),
            "E": (905, 1078),   # angle bas-gauche (station du releve)
        },
        murs=[
            ("A", "B", 102.0),
            ("B", "C", 75.0),
            ("C", "D", 109.0),   # pan coupe
            ("D", "E", 37.0),
            ("E", "A", 93.0),
        ],
        diago=[
            ("E", "B", 136.0),
            ("E", "C", 134.0),
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
            ("J", "A", 48.0),
        ],
        diago=[
            ("J", "B", 116.0),
            ("J", "D", 213.0),   # lecture incertaine sur la photo
            ("J", "G", 236.0),
            ("J", "H", 243.0),
        ],
        equerre=["C", "E", "F"],   # decrochements 33 / 114 / 30 / 29
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


def resoudre(piece: Piece, poids_croquis: float = 0.004,
             iterations: int = 300) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """Retourne les coordonnees des sommets et le rapport d'ecarts."""
    noms = piece.sommets
    idx = {nom: i for i, nom in enumerate(noms)}
    n = len(noms)

    ech = _echelle_croquis(piece)
    # y du croquis vers le bas -> y du dessin vers le haut
    ref = [(piece.pts[nom][0] * ech, -piece.pts[nom][1] * ech) for nom in noms]
    X = [list(p) for p in ref]

    contraintes = piece.contraintes
    lam = 1e-3

    def cout(pos):
        s = 0.0
        for a, b, longueur, _ in contraintes:
            ia, ib = idx[a], idx[b]
            d = math.hypot(pos[ib][0] - pos[ia][0], pos[ib][1] - pos[ia][1])
            s += (d - longueur) ** 2
        for i in range(n):
            s += (poids_croquis * (pos[i][0] - ref[i][0])) ** 2
            s += (poids_croquis * (pos[i][1] - ref[i][1])) ** 2
        return s

    cout_courant = cout(X)

    for _ in range(iterations):
        # Equations normales J^T J dx = -J^T r, construites directement
        m = 2 * n
        JtJ = [[0.0] * m for _ in range(m)]
        Jtr = [0.0] * m

        for a, b, longueur, _ in contraintes:
            ia, ib = idx[a], idx[b]
            dx = X[ib][0] - X[ia][0]
            dy = X[ib][1] - X[ia][1]
            d = math.hypot(dx, dy)
            if d < 1e-9:
                dx, dy, d = 1e-6, 0.0, 1e-6
            r = d - longueur
            ux, uy = dx / d, dy / d
            # d(residu)/d(coord) : -u sur le sommet a, +u sur le sommet b
            g = [(2 * ia, -ux), (2 * ia + 1, -uy), (2 * ib, ux), (2 * ib + 1, uy)]
            for k, gk in g:
                Jtr[k] += gk * r
                for l, gl in g:
                    JtJ[k][l] += gk * gl

        for i in range(n):
            for k, (xi, xr) in enumerate(((X[i][0], ref[i][0]), (X[i][1], ref[i][1]))):
                j = 2 * i + k
                JtJ[j][j] += poids_croquis ** 2
                Jtr[j] += poids_croquis ** 2 * (xi - xr)

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
    return coords, rapport


def orienter(piece: Piece, coords: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Oriente la piece comme sur le croquis.

    Les longueurs seules ne fixent ni la rotation ni le sens de parcours : on
    remet donc la solution en place par un recalage rigide (Kabsch) sur les
    positions du croquis, apres avoir corrige un eventuel effet miroir.
    """
    som = piece.sommets
    ech = _echelle_croquis(piece)
    ref = {s: (piece.pts[s][0] * ech, -piece.pts[s][1] * ech) for s in som}

    def aire_signee(c):
        a = 0.0
        for i, s in enumerate(som):
            p, q = c[s], c[som[(i + 1) % len(som)]]
            a += p[0] * q[1] - q[0] * p[1]
        return a

    if aire_signee(coords) * aire_signee(ref) < 0:      # solution en miroir
        coords = {s: (-x, y) for s, (x, y) in coords.items()}

    n = len(som)
    gx = sum(coords[s][0] for s in som) / n
    gy = sum(coords[s][1] for s in som) / n
    rx = sum(ref[s][0] for s in som) / n
    ry = sum(ref[s][1] for s in som) / n

    # Rotation optimale : angle de la somme des produits croises
    num = sum((coords[s][0] - gx) * (ref[s][1] - ry) - (coords[s][1] - gy) * (ref[s][0] - rx)
              for s in som)
    den = sum((coords[s][0] - gx) * (ref[s][0] - rx) + (coords[s][1] - gy) * (ref[s][1] - ry)
              for s in som)
    th = math.atan2(num, den)
    ct, st = math.cos(th), math.sin(th)
    return {s: (ct * (x - gx) - st * (y - gy), st * (x - gx) + ct * (y - gy))
            for s, (x, y) in coords.items()}


def disposer(pieces_resolues: dict[str, dict[str, tuple[float, float]]],
             ecart: float = 120.0) -> None:
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
        if piece.diago:
            L.append("CLAYER")
            L.append("DIAGONALES")
            for a, b, _l in piece.diago:
                L += ["_.LINE",
                      f"{_n(coords[a][0])},{_n(coords[a][1])}",
                      f"{_n(coords[b][0])},{_n(coords[b][1])}",
                      ""]

        # --- cotes (texte au milieu de chaque segment)
        for a, b, longueur in piece.murs + piece.diago:   # pas les equerres supposees
            L.append(_texte_lisp("COTES", _milieu(coords[a], coords[b]), H_COTE,
                                 _angle_texte(coords[a], coords[b]), f"{longueur:g}"))

        # --- nom de la piece au centre
        cx = sum(coords[s][0] for s in piece.sommets) / len(piece.sommets)
        cy = sum(coords[s][1] for s in piece.sommets) / len(piece.sommets)
        L.append(_texte_lisp("NOMS", (cx, cy), H_NOM, 0.0, piece.nom))

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

    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LAYER"); g(70, len(CALQUES))
    for nom, couleur in CALQUES:
        g(0, "LAYER"); g(2, nom); g(70, 0); g(62, couleur); g(6, "CONTINUOUS")
    g(0, "ENDTAB"); g(0, "ENDSEC")

    g(0, "SECTION"); g(2, "ENTITIES")

    def ligne(calque, p, q):
        g(0, "LINE"); g(8, calque)
        g(10, float(p[0])); g(20, float(p[1])); g(30, 0.0)
        g(11, float(q[0])); g(21, float(q[1])); g(31, 0.0)

    def texte(calque, p, hauteur, angle, contenu):
        g(0, "TEXT"); g(8, calque)
        g(10, float(p[0])); g(20, float(p[1])); g(30, 0.0)
        g(40, float(hauteur)); g(1, contenu); g(50, float(angle))
        g(72, 1); g(73, 2)                       # justification centre / milieu
        g(11, float(p[0])); g(21, float(p[1])); g(31, 0.0)

    for piece in PIECES:
        coords = solutions[piece.nom]
        sommets = piece.sommets
        for i, s in enumerate(sommets):
            ligne("MURS", coords[s], coords[sommets[(i + 1) % len(sommets)]])
        for a, b, _l in piece.diago:
            ligne("DIAGONALES", coords[a], coords[b])
        for a, b, longueur in piece.murs + piece.diago:   # pas les equerres supposees
            texte("COTES", _milieu(coords[a], coords[b]), H_COTE,
                  _angle_texte(coords[a], coords[b]), f"{longueur:g}")
        cx = sum(coords[s][0] for s in sommets) / len(sommets)
        cy = sum(coords[s][1] for s in sommets) / len(sommets)
        texte("NOMS", (cx, cy), H_NOM, 0.0, piece.nom)

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
        for a, b, _l in piece.diago:
            pa, pb = T(coords[a]), T(coords[b])
            s.append(f'<line x1="{pa[0]:.2f}" y1="{pa[1]:.2f}" x2="{pb[0]:.2f}" '
                     f'y2="{pb[1]:.2f}" stroke="#8898a8" stroke-width="1.6"/>')
        for a, b, longueur in piece.murs + piece.diago:   # pas les equerres supposees
            mx, my = T(_milieu(coords[a], coords[b]))
            ang = -_angle_texte(coords[a], coords[b])
            s.append(f'<text x="{mx:.2f}" y="{my:.2f}" font-size="15" fill="#222" '
                     f'text-anchor="middle" dominant-baseline="middle" '
                     f'transform="rotate({ang:.1f} {mx:.2f} {my:.2f})">{longueur:g}</text>')
        cx = sum(T(coords[s_])[0] for s_ in piece.sommets) / len(piece.sommets)
        cy = sum(T(coords[s_])[1] for s_ in piece.sommets) / len(piece.sommets)
        s.append(f'<text x="{cx:.2f}" y="{cy:.2f}" font-size="26" fill="#8a2a20" '
                 f'text-anchor="middle" opacity="0.65">{piece.nom}</text>')

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
        solutions[piece.nom] = orienter(piece, coords)
        rapports[piece.nom] = rapport

    disposer(solutions)

    print("RAPPORT DE COHERENCE DU RELEVE")
    print("=" * 66)
    suspects: list[str] = []
    for piece in PIECES:
        n = len(piece.sommets)
        manquantes = max(0, (n - 3) - len(piece.diago) - len(piece.equerre))
        aire = 0.0
        c = solutions[piece.nom]
        som = piece.sommets
        for i, s in enumerate(som):
            p, q = c[s], c[som[(i + 1) % n]]
            aire += p[0] * q[1] - q[0] * p[1]
        aire = abs(aire) / 2.0

        print(f"\n{piece.nom} : {n} sommets, surface {aire / 10000:.2f} m2")
        if manquantes:
            print(f"  /!\\ {manquantes} diagonale(s) manquante(s) : la forme reste "
                  f"partiellement libre, l'allure du croquis est conservee.")
        for r in rapports[piece.nom]:
            drapeau = ""
            if abs(r["ecart"]) > 3.0:
                drapeau = "   <<< A VERIFIER"
                suspects.append(f"{piece.nom} {r['a']}-{r['b']} "
                                f"({r['genre']} {r['releve']:g})")
            print(f"  {r['a']}-{r['b']:<2} {r['genre']:<10} releve {r['releve']:>7.1f} "
                  f"  calcule {r['obtenu']:>7.1f}   ecart {r['ecart']:+6.1f}{drapeau}")

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
