#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
releve2plan -- d'un releve de terrain par triangulation vers un plan AutoCAD.

    python3 releve2plan.py mon_releve.txt

Produit, a cote du fichier de releve : un DXF (R12, ouvrable directement dans
AutoCAD), un script SCR, et un apercu SVG. Affiche un rapport de coherence et
un diagnostic des cotes qui ne collent pas.

Aucune dependance : Python 3.9+ suffit.


Le probleme
-----------
Un releve d'appartement au metre donne des LONGUEURS et aucun angle : les murs
de chaque piece, plus quelques diagonales pour "trianguler". Ca ne suffit pas :
pour figer un polygone a N sommets par les seules distances, il faudrait N-3
diagonales, ce qu'on ne releve quasiment jamais sur le terrain.

L'information manquante est sur le croquis, sous les yeux : la DIRECTION de
chaque mur. Un mur dessine horizontal est horizontal. C'est gratuit a noter et
ca redresse tout le plan.

D'ou le format de saisie : pour chaque mur, sa longueur et sa direction.


Format du fichier de releve
---------------------------
Un fichier texte. Les lignes vides et tout ce qui suit un "#" sont ignores.
Les longueurs se notent avec un point ou une virgule decimale, peu importe.

    PIECE Sejour
        MUR  326  E          # 326 cm vers l'est (la droite)
        MUR  399  S
        MUR  166  O
        MUR   25  N
        MUR   88  O
        MUR  100  NO         # pan coupe : direction approximative
        MUR  268  N          # le polygone se referme tout seul
        DIAG A E 404         # diagonale entre les sommets A et E
        DIAG B E 402
        RANGEE 0             # facultatif : ligne de la mise en page

Les sommets sont nommes tout seuls dans l'ordre des murs : A est le point de
depart, B la fin du premier mur, C la fin du deuxieme, etc. Le dernier mur
revient sur A. Le rapport et le dessin utilisent ces memes lettres, donc pour
lire une diagonale il suffit de compter les murs sur le croquis.

Directions admises :

    E N O S          (ou W pour l'ouest) -- murs mis EXACTEMENT d'equerre
    NE NO SE SO      (ou NW, SW)         -- direction indicative
    145              un angle en degres  -- direction indicative
                                            (0 = est, sens trigonometrique)

Seules les quatre directions cardinales sont mises d'equerre : un trait oblique
a main levee vaut bien moins qu'une equerre, il est donc pris avec un poids
plus faible et c'est la mesure qui tranche.

Une diagonale tracee sur le croquis mais dont le chiffre est illisible se note
avec un point d'interrogation -- elle sera signalee, mais ni utilisee ni cotee :

    DIAG B E ?


Comment le plan est calcule
---------------------------
Moindres carres amortis (Levenberg-Marquardt) sur deux familles de residus,
toutes deux exprimees dans l'unite du releve :

    longueur   : ||Pi - Pj|| - longueur relevee
    direction  : deport perpendiculaire du mur par rapport a sa direction

Le residu de direction est lineaire en les coordonnees et sans echelle : il
oriente le mur sans rien dire de sa longueur. Les mesures restent donc
maitresses de la geometrie, le croquis de l'orientation.


Le diagnostic
-------------
Sur un releve manuscrit, l'erreur habituelle n'est pas la mesure : c'est la
transcription (un chiffre mal lu, une diagonale rattachee au mauvais angle).
Le programme construit donc d'abord chaque piece SANS ses diagonales, a partir
des seuls murs et de leurs directions, puis :

  * regarde de combien la piece ne se referme pas, et propose la cote de mur
    qui la refermerait ;
  * si un seul mur est oblique, en deduit sa longueur et son angle reels ;
  * confronte chaque diagonale relevee a toutes les paires de sommets, et
    signale quand une autre paire correspond nettement mieux.

C'est ce qui permet de dire "votre 213 correspond a J-F (211), pas a J-D (138)"
au lieu de simplement constater que quelque chose cloche.
"""

from __future__ import annotations

import argparse
import itertools
import math
import os
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Lecture du fichier de releve
# ---------------------------------------------------------------------------

CARDINALES = {"E": 0.0, "N": 90.0, "O": 180.0, "W": 180.0, "S": 270.0}
OBLIQUES = {"NE": 45.0, "NO": 135.0, "NW": 135.0,
            "SO": 225.0, "SW": 225.0, "SE": 315.0}


class ErreurReleve(Exception):
    """Erreur de saisie dans le fichier de releve, signalee avec sa ligne."""


@dataclass
class Mur:
    a: str
    b: str
    longueur: float
    angle: float
    cardinale: bool          # True = mis exactement d'equerre


@dataclass
class Piece:
    nom: str
    murs: list[Mur] = field(default_factory=list)
    diago: list[tuple[str, str, float | None]] = field(default_factory=list)
    rangee: int | None = None

    @property
    def sommets(self) -> list[str]:
        return [m.a for m in self.murs]

    @property
    def diago_cotees(self) -> list[tuple[str, str, float]]:
        return [(a, b, l) for a, b, l in self.diago if l is not None]

    @property
    def contraintes(self) -> list[tuple[str, str, float, str]]:
        return ([(m.a, m.b, m.longueur, "mur") for m in self.murs]
                + [(a, b, l, "diagonale") for a, b, l in self.diago_cotees])


def nom_sommet(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    nom = ""
    i += 1
    while i:
        i, reste = divmod(i - 1, 26)
        nom = chr(ord("A") + reste) + nom
    return nom


def _nombre(texte: str, ligne: int, quoi: str) -> float:
    try:
        return float(texte.replace(",", "."))
    except ValueError:
        raise ErreurReleve(f"ligne {ligne} : {quoi} illisible ({texte!r})")


def _direction(texte: str, ligne: int) -> tuple[float, bool]:
    jeton = texte.upper()
    if jeton in CARDINALES:
        return CARDINALES[jeton], True
    if jeton in OBLIQUES:
        return OBLIQUES[jeton], False
    try:
        return float(texte.replace(",", ".")) % 360.0, False
    except ValueError:
        raise ErreurReleve(
            f"ligne {ligne} : direction inconnue ({texte!r}). Attendu : "
            f"E N O S, NE NO SE SO, ou un angle en degres.")


def lire_releve(chemin: str) -> list[Piece]:
    pieces: list[Piece] = []
    courante: Piece | None = None

    with open(chemin, encoding="utf-8") as f:
        for no, brut in enumerate(f, 1):
            ligne = brut.split("#", 1)[0].strip()
            if not ligne:
                continue
            mots = ligne.split()
            cle = mots[0].upper()

            if cle == "PIECE":
                if len(mots) < 2:
                    raise ErreurReleve(f"ligne {no} : PIECE sans nom")
                courante = Piece(nom=" ".join(mots[1:]))
                pieces.append(courante)
                continue

            if courante is None:
                raise ErreurReleve(
                    f"ligne {no} : '{cle}' rencontre avant toute declaration PIECE")

            if cle == "MUR":
                if len(mots) != 3:
                    raise ErreurReleve(
                        f"ligne {no} : attendu 'MUR <longueur> <direction>'")
                longueur = _nombre(mots[1], no, "longueur de mur")
                if longueur <= 0:
                    raise ErreurReleve(f"ligne {no} : longueur de mur nulle ou negative")
                angle, cardinale = _direction(mots[2], no)
                i = len(courante.murs)
                courante.murs.append(Mur(nom_sommet(i), nom_sommet(i + 1),
                                         longueur, angle, cardinale))

            elif cle == "DIAG":
                if len(mots) != 4:
                    raise ErreurReleve(
                        f"ligne {no} : attendu 'DIAG <sommet> <sommet> <longueur|?>'")
                a, b = mots[1].upper(), mots[2].upper()
                if a == b:
                    raise ErreurReleve(f"ligne {no} : diagonale d'un sommet vers lui-meme")
                longueur = None if mots[3] == "?" else _nombre(mots[3], no, "longueur")
                courante.diago.append((a, b, longueur))

            elif cle == "RANGEE":
                if len(mots) != 2:
                    raise ErreurReleve(f"ligne {no} : attendu 'RANGEE <numero>'")
                courante.rangee = int(_nombre(mots[1], no, "numero de rangee"))

            else:
                raise ErreurReleve(
                    f"ligne {no} : mot-cle inconnu {mots[0]!r}. "
                    f"Attendu : PIECE, MUR, DIAG ou RANGEE.")

    if not pieces:
        raise ErreurReleve("aucune piece dans le fichier")

    for p in pieces:
        if len(p.murs) < 3:
            raise ErreurReleve(f"{p.nom} : {len(p.murs)} mur(s), il en faut au moins 3")
        # le dernier mur reboucle sur le premier sommet
        p.murs[-1].b = p.murs[0].a
        connus = set(p.sommets)
        for a, b, _l in p.diago:
            for s in (a, b):
                if s not in connus:
                    raise ErreurReleve(
                        f"{p.nom} : la diagonale {a}-{b} cite le sommet {s}, "
                        f"or la piece va de A a {p.sommets[-1]}")

    # rangees par defaut : 3 pieces par ligne
    if all(p.rangee is None for p in pieces):
        for i, p in enumerate(pieces):
            p.rangee = i // 3
    else:
        for p in pieces:
            if p.rangee is None:
                p.rangee = 0
    return pieces


# ---------------------------------------------------------------------------
# Solveur
# ---------------------------------------------------------------------------

def _resoudre_systeme(A: list[list[float]], b: list[float]) -> list[float]:
    """Gauss avec pivot partiel."""
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


def amorce(piece: Piece) -> dict[str, tuple[float, float]]:
    """Parcours du contour : longueurs relevees suivant les directions donnees.

    Le polygone ne se referme generalement pas exactement -- c'est normal et
    c'est meme la matiere premiere du diagnostic. Il sert de point de depart.
    """
    pos = {piece.murs[0].a: (0.0, 0.0)}
    x = y = 0.0
    for m in piece.murs[:-1]:
        x += m.longueur * math.cos(math.radians(m.angle))
        y += m.longueur * math.sin(math.radians(m.angle))
        pos[m.b] = (x, y)
    return pos


def resoudre(piece: Piece, avec_diagonales: bool = True,
             poids_cardinale: float = 1.0, poids_oblique: float = 0.15,
             iterations: int = 400) -> tuple[dict[str, tuple[float, float]], dict]:
    noms = piece.sommets
    idx = {nom: i for i, nom in enumerate(noms)}
    n = len(noms)

    depart = amorce(piece)
    X = [list(depart[s]) for s in noms]

    contraintes = piece.contraintes if avec_diagonales else \
        [(m.a, m.b, m.longueur, "mur") for m in piece.murs]

    directions = []
    for m in piece.murs:
        directions.append({
            "a": m.a, "b": m.b, "angle": m.angle,
            "cardinale": m.cardinale,
            "poids": poids_cardinale if m.cardinale else poids_oblique,
            "sin": math.sin(math.radians(m.angle)),
            "cos": math.cos(math.radians(m.angle))})
    lam = 1e-3

    def ecart_direction(pos, d) -> float:
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
        return s

    cout_courant = cout(X)

    for _ in range(iterations):
        m_ = 2 * n
        JtJ = [[0.0] * m_ for _ in range(m_)]
        Jtr = [0.0] * m_

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
            accumuler([(2 * ia, -ux), (2 * ia + 1, -uy),
                       (2 * ib, ux), (2 * ib + 1, uy)], d - longueur)

        for d in directions:
            ia, ib = idx[d["a"]], idx[d["b"]]
            w, si, co = d["poids"], d["sin"], d["cos"]
            accumuler([(2 * ia, w * si), (2 * ia + 1, -w * co),
                       (2 * ib, -w * si), (2 * ib + 1, w * co)],
                      w * ecart_direction(X, d))

        # ancrage tres faible du premier sommet : fige la translation
        JtJ[0][0] += 1e-6
        JtJ[1][1] += 1e-6
        Jtr[0] += 1e-6 * X[0][0]
        Jtr[1] += 1e-6 * X[0][1]

        for j in range(m_):
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

    cotes = []
    for a, b, longueur, genre in piece.contraintes:
        obtenu = math.dist(coords[a], coords[b])
        cotes.append({"a": a, "b": b, "genre": genre, "releve": longueur,
                      "obtenu": obtenu, "ecart": obtenu - longueur})
    angles = []
    for m in piece.murs:
        (xa, ya), (xb, yb) = coords[m.a], coords[m.b]
        obtenu = math.degrees(math.atan2(yb - ya, xb - xa))
        angles.append({"a": m.a, "b": m.b, "cardinale": m.cardinale,
                       "angle": m.angle,
                       "ecart": (obtenu - m.angle + 180.0) % 360.0 - 180.0})
    return coords, {"cotes": cotes, "angles": angles}


def surface(coords, sommets) -> float:
    n = len(sommets)
    a = sum(coords[sommets[i]][0] * coords[sommets[(i + 1) % n]][1]
            - coords[sommets[(i + 1) % n]][0] * coords[sommets[i]][1]
            for i in range(n))
    return abs(a) / 2.0


# ---------------------------------------------------------------------------
# Diagnostic : retrouver les cotes mal transcrites
# ---------------------------------------------------------------------------

def diagnostiquer(piece: Piece, tol_fermeture: float = 3.0,
                  tol_diagonale: float = 8.0) -> list[str]:
    """Confronte le releve a la piece reconstruite sans ses diagonales."""
    remarques: list[str] = []

    # Un releve au metre se referme rarement au centimetre pres : on ne
    # commente la fermeture que bien au-dela du bruit de mesure normal.
    seuil_cardinal = 3.0 * tol_fermeture
    seuil_oblique = 2.0 * tol_fermeture

    # --- 1. Le contour se referme-t-il ?
    dx = sum(m.longueur * math.cos(math.radians(m.angle)) for m in piece.murs)
    dy = sum(m.longueur * math.sin(math.radians(m.angle)) for m in piece.murs)
    obliques = [m for m in piece.murs if not m.cardinale]

    if not obliques:
        if max(abs(dx), abs(dy)) > seuil_cardinal:
            remarques.append(
                f"le contour ne se referme pas : {dx:+.1f} en horizontal, "
                f"{dy:+.1f} en vertical.")
            for m in piece.murs:
                c = round(math.cos(math.radians(m.angle)))
                s = round(math.sin(math.radians(m.angle)))
                # mur horizontal : il pese sur dx ; vertical : sur dy
                manque, signe = (dx, c) if c else (dy, s)
                if abs(manque) <= seuil_cardinal:
                    continue
                propose = m.longueur - signe * manque
                if propose > 0:
                    remarques.append(
                        f"   le mur {m.a}-{m.b} a {m.longueur:g} refermerait la "
                        f"piece a {propose:.0f}")
    elif len(obliques) == 1:
        # le mur oblique encaisse tout le reste du contour : on le deduit
        seul = obliques[0]
        vx = seul.longueur * math.cos(math.radians(seul.angle)) - dx
        vy = seul.longueur * math.sin(math.radians(seul.angle)) - dy
        deduite = math.hypot(vx, vy)
        if abs(deduite - seul.longueur) > seuil_oblique:
            remarques.append(
                f"le pan coupe {seul.a}-{seul.b} releve a {seul.longueur:g} doit "
                f"mesurer {deduite:.0f} pour que la piece se referme "
                f"(angle deduit {math.degrees(math.atan2(vy, vx)) % 360:.0f} deg).")
    else:
        residu = math.hypot(dx, dy)
        if residu > seuil_cardinal:
            remarques.append(
                f"le contour ne se referme pas ({residu:.1f} d'ecart) ; avec "
                f"{len(obliques)} murs obliques, impossible de designer un "
                f"responsable.")

    # Un contour qui ne ferme pas fausse le squelette : tant qu'il n'est pas
    # corrige, les distances calculees sont fausses et il ne sert a rien de
    # proposer un rattachement de diagonale. On signale sans suggerer.
    fermeture_douteuse = bool(remarques)

    # --- 2. Chaque diagonale est-elle rattachee aux bons sommets ?
    if piece.diago_cotees:
        squelette, _ = resoudre(piece, avec_diagonales=False)
        som = piece.sommets
        # une suggestion ne doit proposer ni un mur, ni une paire deja relevee
        prises = ({frozenset((m.a, m.b)) for m in piece.murs}
                  | {frozenset((a, b)) for a, b, _l in piece.diago_cotees})
        paires = {(a, b): math.dist(squelette[a], squelette[b])
                  for a, b in itertools.combinations(som, 2)}
        for a, b, longueur in piece.diago_cotees:
            actuel = paires.get((a, b)) or paires[(b, a)]
            if abs(actuel - longueur) <= tol_diagonale:
                continue
            if fermeture_douteuse:
                remarques.append(
                    f"la diagonale {a}-{b} relevee a {longueur:g} mesure "
                    f"{actuel:.0f}, mais corrigez d'abord la fermeture "
                    f"ci-dessus : elle fausse ce calcul.")
                continue
            libres = sorted(((p, d) for p, d in paires.items()
                             if frozenset(p) not in prises),
                            key=lambda kv: abs(kv[1] - longueur))
            if libres and abs(libres[0][1] - longueur) < abs(actuel - longueur) / 2:
                (ma, mb), md = libres[0]
                remarques.append(
                    f"la diagonale {a}-{b} relevee a {longueur:g} mesure "
                    f"{actuel:.0f} : elle correspond plutot a {ma}-{mb} "
                    f"({md:.0f}).")
            else:
                remarques.append(
                    f"la diagonale {a}-{b} relevee a {longueur:g} mesure "
                    f"{actuel:.0f} ; aucune autre paire ne correspond mieux.")
    return remarques


# ---------------------------------------------------------------------------
# Mise en page
# ---------------------------------------------------------------------------

def disposer(pieces: list[Piece], solutions: dict, ecart: float) -> None:
    """Pose les pieces cote a cote : un releve ne dit rien de leur position
    relative, chacune ayant ete mesuree separement."""
    def bbox(c):
        xs = [p[0] for p in c.values()]
        ys = [p[1] for p in c.values()]
        return min(xs), min(ys), max(xs), max(ys)

    y_haut = 0.0
    for rangee in sorted({p.rangee for p in pieces}):
        de_la_rangee = [p for p in pieces if p.rangee == rangee]
        hauteur = max(bbox(solutions[p.nom])[3] - bbox(solutions[p.nom])[1]
                      for p in de_la_rangee)
        x_gauche = 0.0
        for p in de_la_rangee:
            c = solutions[p.nom]
            x0, y0, x1, _ = bbox(c)
            ddx, ddy = x_gauche - x0, (y_haut - hauteur) - y0
            for k in c:
                c[k] = (c[k][0] + ddx, c[k][1] + ddy)
            x_gauche += (x1 - x0) + ecart
        y_haut -= hauteur + ecart


# ---------------------------------------------------------------------------
# Ecriture des fichiers
# ---------------------------------------------------------------------------

CALQUES = [("MURS", 1), ("DIAGONALES", 8), ("COTES", 3), ("NOMS", 4)]


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


def _pose_nom(coords, sommets, h_nom):
    """Nom de la piece juste au-dessus du polygone, pour ne masquer aucune cote."""
    xs = [coords[s][0] for s in sommets]
    ys = [coords[s][1] for s in sommets]
    hauteur = max(h_nom / 2.0, min(h_nom, (max(xs) - min(xs)) / 6.0))
    return ((min(xs) + max(xs)) / 2.0, max(ys) + hauteur), hauteur


def _cotations(piece: Piece):
    return ([(m.a, m.b, m.longueur) for m in piece.murs]
            + list(piece.diago_cotees))


def ecrire_dxf(chemin, pieces, solutions, h_cote, h_nom) -> None:
    out: list[str] = []

    def g(code: int, valeur) -> None:
        out.append(str(code))
        out.append(f"{valeur:.4f}" if isinstance(valeur, float) else str(valeur))

    xs = [p[0] for c in solutions.values() for p in c.values()]
    ys = [p[1] for c in solutions.values() for p in c.values()]

    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$DWGCODEPAGE"); g(3, "ANSI_1252")
    g(9, "$INSBASE"); g(10, 0.0); g(20, 0.0); g(30, 0.0)
    g(9, "$EXTMIN"); g(10, min(xs)); g(20, min(ys)); g(30, 0.0)
    g(9, "$EXTMAX"); g(10, max(xs)); g(20, max(ys)); g(30, 0.0)
    g(9, "$LIMMIN"); g(10, min(xs)); g(20, min(ys))
    g(9, "$LIMMAX"); g(10, max(xs)); g(20, max(ys))
    g(9, "$INSUNITS"); g(70, 5)               # 5 = centimetres
    g(9, "$LUNITS"); g(70, 2)
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
        """POLYLINE R12 : un seul objet (deplacer, DECALER, AIRE > Objet)."""
        g(0, "POLYLINE"); g(8, calque); g(66, 1); g(70, 1)
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
        g(7, "STANDARD"); g(72, 1); g(73, 2)
        g(11, float(p[0])); g(21, float(p[1])); g(31, 0.0)

    for piece in pieces:
        coords = solutions[piece.nom]
        sommets = piece.sommets
        polyligne_fermee("MURS", [coords[s] for s in sommets])
        for a, b, _l in piece.diago_cotees:
            ligne("DIAGONALES", coords[a], coords[b])
        for a, b, longueur in _cotations(piece):
            texte("COTES", _milieu(coords[a], coords[b]), h_cote,
                  _angle_texte(coords[a], coords[b]), f"{longueur:g}")
        pos, h = _pose_nom(coords, sommets, h_nom)
        texte("NOMS", pos, h, 0.0, piece.nom)

    g(0, "ENDSEC"); g(0, "EOF")

    with open(chemin, "w", encoding="cp1252", errors="replace", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")


def _texte_lisp(calque, p, hauteur, angle_deg, contenu) -> str:
    """Texte centre cree par entmake.

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


def ecrire_scr(chemin, pieces, solutions, h_cote, h_nom) -> None:
    L: list[str] = []
    # commandes prefixees par _ et . : fonctionne aussi sur AutoCAD francais
    L += ["CMDECHO", "0", "OSMODE", "0", "BLIPMODE", "0"]
    L += ["_.UNDO", "_BEgin"]
    L.append("_.-LAYER")
    for nom, couleur in CALQUES:
        L += ["_Make", nom, "_Color", str(couleur), ""]
    L.append("")

    for piece in pieces:
        coords = solutions[piece.nom]
        L += ["CLAYER", "MURS", "_.PLINE"]
        L += [f"{coords[s][0]:.3f},{coords[s][1]:.3f}" for s in piece.sommets]
        L += ["_Close"]
        if piece.diago_cotees:
            L += ["CLAYER", "DIAGONALES"]
            for a, b, _l in piece.diago_cotees:
                L += ["_.LINE", f"{coords[a][0]:.3f},{coords[a][1]:.3f}",
                      f"{coords[b][0]:.3f},{coords[b][1]:.3f}", ""]
        for a, b, longueur in _cotations(piece):
            L.append(_texte_lisp("COTES", _milieu(coords[a], coords[b]), h_cote,
                                 _angle_texte(coords[a], coords[b]), f"{longueur:g}"))
        pos, h = _pose_nom(coords, piece.sommets, h_nom)
        L.append(_texte_lisp("NOMS", pos, h, 0.0, piece.nom))

    L += ["CLAYER", "MURS", "_.ZOOM", "_Extents", "_.UNDO", "_End", "CMDECHO", "1"]
    with open(chemin, "w", encoding="cp1252", errors="replace", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")


def _echapper(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ecrire_svg(chemin, pieces, solutions, h_cote, h_nom) -> None:
    xs = [p[0] for c in solutions.values() for p in c.values()]
    ys = [p[1] for c in solutions.values() for p in c.values()]
    marge = h_nom * 3
    x0, x1 = min(xs) - marge, max(xs) + marge
    y0, y1 = min(ys) - marge, max(ys) + marge
    larg, haut = x1 - x0, y1 - y0

    def T(p):
        return (p[0] - x0, y1 - p[1])

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larg:.1f} {haut:.1f}" '
         f'width="1100" font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{larg:.1f}" height="{haut:.1f}" fill="#fbfaf8"/>']

    for piece in pieces:
        coords = solutions[piece.nom]
        pts = " ".join(f"{T(coords[v])[0]:.2f},{T(coords[v])[1]:.2f}"
                       for v in piece.sommets)
        s.append(f'<polygon points="{pts}" fill="#e8434322" stroke="#e04030" '
                 f'stroke-width="{h_cote / 2:.1f}" stroke-linejoin="round"/>')
        for a, b, _l in piece.diago_cotees:
            pa, pb = T(coords[a]), T(coords[b])
            s.append(f'<line x1="{pa[0]:.2f}" y1="{pa[1]:.2f}" x2="{pb[0]:.2f}" '
                     f'y2="{pb[1]:.2f}" stroke="#8898a8" stroke-width="{h_cote / 8:.2f}"/>')
        for a, b, longueur in _cotations(piece):
            mx, my = T(_milieu(coords[a], coords[b]))
            ang = -_angle_texte(coords[a], coords[b])
            s.append(f'<text x="{mx:.2f}" y="{my:.2f}" font-size="{h_cote:.1f}" '
                     f'fill="#222" text-anchor="middle" dominant-baseline="middle" '
                     f'transform="rotate({ang:.1f} {mx:.2f} {my:.2f})">{longueur:g}</text>')
        pos, h = _pose_nom(coords, piece.sommets, h_nom)
        nx, ny = T(pos)
        s.append(f'<text x="{nx:.2f}" y="{ny:.2f}" font-size="{h:.1f}" fill="#8a2a20" '
                 f'text-anchor="middle" opacity="0.8">{_echapper(piece.nom)}</text>')

    s.append('</svg>')
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(s))


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Reconstruit un plan a partir d'un releve par triangulation "
                    "et l'exporte vers AutoCAD (DXF, SCR) avec un apercu SVG.",
        epilog="Le format du fichier de releve est decrit en tete de ce script.")
    ap.add_argument("releve", help="fichier de releve (voir le format en tete de script)")
    ap.add_argument("-o", "--sortie", metavar="DOSSIER",
                    help="dossier de sortie (par defaut : celui du releve)")
    ap.add_argument("--prefixe", help="nom de base des fichiers produits "
                                      "(par defaut : celui du releve)")
    ap.add_argument("--poids-axe", type=float, default=1.0, metavar="P",
                    help="force de l'equerrage des murs cardinaux (defaut 1.0 ; "
                         "0 = ignorer les directions et n'utiliser que les mesures)")
    ap.add_argument("--tolerance", type=float, default=3.0, metavar="T",
                    help="ecart au-dela duquel une cote est signalee (defaut 3)")
    args = ap.parse_args(argv)

    try:
        pieces = lire_releve(args.releve)
    except (OSError, ErreurReleve, ValueError) as e:
        print(f"Releve illisible : {e}", file=sys.stderr)
        return 2

    solutions, rapports = {}, {}
    for p in pieces:
        coords, rapport = resoudre(p, poids_cardinale=args.poids_axe)
        solutions[p.nom], rapports[p.nom] = coords, rapport

    # echelle des textes : proportionnelle a la taille reelle du releve
    longueurs = sorted(m.longueur for p in pieces for m in p.murs)
    h_cote = max(1.0, 0.045 * longueurs[len(longueurs) // 2])
    h_nom = h_cote * 2.0
    disposer(pieces, solutions, ecart=h_nom * 6)

    print("RAPPORT DE COHERENCE DU RELEVE")
    print("=" * 70)
    suspects = []
    for p in pieces:
        aire = surface(solutions[p.nom], p.sommets)
        print(f"\n{p.nom} : {len(p.sommets)} sommets ({p.sommets[0]}..{p.sommets[-1]}), "
              f"surface {aire / 10000:.2f} m2")
        for a, b, l in p.diago:
            if l is None:
                print(f"  {a}-{b:<2} diagonale tracee mais cote illisible : non utilisee")
        for r in rapports[p.nom]["cotes"]:
            drapeau = ""
            if abs(r["ecart"]) > args.tolerance:
                drapeau = "   <<<"
                suspects.append(f"{p.nom} {r['a']}-{r['b']} "
                                f"({r['genre']} {r['releve']:g})")
            print(f"  {r['a']}-{r['b']:<2} {r['genre']:<10} releve {r['releve']:>7.1f}"
                  f"   calcule {r['obtenu']:>7.1f}   ecart {r['ecart']:+6.1f}{drapeau}")
        for ang in rapports[p.nom]["angles"]:
            if ang["cardinale"] and abs(ang["ecart"]) > 1.5:
                print(f"  {ang['a']}-{ang['b']:<2} mur declare d'equerre mais devie "
                      f"de {ang['ecart']:+.1f} deg pour respecter les cotes")

    print("\n" + "=" * 70)
    print("DIAGNOSTIC  (piece reconstruite a partir des seuls murs)")
    quelque_chose = False
    for p in pieces:
        remarques = diagnostiquer(p, tol_fermeture=args.tolerance)
        if remarques:
            quelque_chose = True
            print(f"\n{p.nom} :")
            for r in remarques:
                print(("  " if r.startswith("   ") else "  - ") + r)
    if not quelque_chose:
        print("\nRien a signaler : murs et diagonales concordent.")

    print("\n" + "=" * 70)
    if suspects:
        print(f"Cotes s'ecartant de plus de {args.tolerance:g} :")
        for s in suspects:
            print("  - " + s)
    else:
        print(f"Toutes les cotes tombent a moins de {args.tolerance:g}.")

    dossier = args.sortie or os.path.dirname(os.path.abspath(args.releve))
    os.makedirs(dossier, exist_ok=True)
    base = args.prefixe or os.path.splitext(os.path.basename(args.releve))[0]
    sorties = []
    for ext, fonction in (("dxf", ecrire_dxf), ("scr", ecrire_scr), ("svg", ecrire_svg)):
        chemin = os.path.join(dossier, f"{base}.{ext}")
        fonction(chemin, pieces, solutions, h_cote, h_nom)
        sorties.append(chemin)

    print("\nFichiers generes :")
    for f in sorties:
        print("  " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
