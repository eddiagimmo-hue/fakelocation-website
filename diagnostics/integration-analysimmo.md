# Intégration AnalysImmo — accès base SQL

## Ce que dit l'éditeur

Réponse d'Atlibitum (service client, 31/03/2026) à la question « la licence donne-t-elle
accès aux Web Services pour piloter l'application depuis une application externe ? » :

> « Oui, c'est lié à votre base de données au serveur (SQL qui est librement accessible). »

Autrement dit : **pas de Web Service documenté, mais un accès direct à la base SQL**.
C'est jouable, et même plus rapide qu'une API — mais ça déplace toute la responsabilité
de l'intégrité des données sur nous.

## Ce qu'il faut établir avant d'écrire la moindre ligne

1. **Moteur et version** : SQL Server / SQL Server Express, MySQL, Firebird, PostgreSQL ?
   À lire dans les services Windows du PC, ou dans le fichier de configuration
   d'AnalysImmo (chaîne de connexion).
2. **Chaîne de connexion** : hôte, port, instance, identifiants. Le serveur est-il sur le
   PC lui-même ou sur une machine du réseau ?
3. **Procédure de sauvegarde** : savoir restaurer la base avant de tester quoi que ce soit.
4. **Confirmation écrite de l'éditeur** que l'écriture directe en base ne fait pas sauter
   le support ni la garantie. La réponse ci-dessus autorise l'accès, elle ne dit pas
   explicitement « vous pouvez écrire ». À faire préciser par mail — ça ne coûte rien et
   ça vous couvre.

## La méthode pour cartographier les tables : le diff

C'est la technique qui fait gagner des semaines. Aucune documentation n'est nécessaire.

1. Créer un dossier vide dans AnalysImmo. Dump complet de la base → `t0.sql`.
2. Saisir **une seule** observation amiante à la main dans le logiciel. Dump → `t1.sql`.
3. `diff t0.sql t1.sql` : les lignes ajoutées vous donnent exactement les tables, colonnes
   et clés étrangères qui portent une observation amiante.
4. Recommencer en changeant **un seul champ** (l'état de conservation, par exemple) pour
   identifier la colonne et les valeurs codées réellement utilisées.
5. Répéter par module. Compter une demi-journée par module.

C'est ce diff, et pas les schémas JSON, qui donnera la table de correspondance finale
entre nos énumérations et les codes internes d'AnalysImmo.

## Règles de sécurité pour l'écriture

- **Jamais sur la base de production tant que la cartographie n'est pas figée.** Travailler
  sur une copie restaurée, sur une VM ou un second poste.
- **Lecture d'abord** : le premier connecteur qui marche doit être un connecteur en lecture
  seule qui relit un dossier existant. Si on sait relire, on saura écrire.
- **Respecter les clés et compteurs internes** : beaucoup de logiciels de bureau gèrent
  eux-mêmes des séquences d'identifiants, des compteurs de dossier, parfois des champs de
  contrôle. Insérer une ligne « à la main » sans mettre à jour ces compteurs corrompt le
  dossier de façon silencieuse.
- **AnalysImmo ne doit pas tourner pendant l'écriture** (verrous, cache applicatif).
  Écrire base fermée, puis ouvrir le logiciel et vérifier visuellement le rendu.
- **Sauvegarde automatique avant chaque injection**, sans exception.
- **Vérification humaine systématique** : après injection, on ouvre le dossier dans
  AnalysImmo et on relit la grille avant de générer le rapport. L'injection ne remplace
  pas la relecture, elle remplace la frappe.

## Chemin de repli

Si l'écriture directe s'avère trop risquée (compteurs opaques, contraintes non
documentées, refus de l'éditeur), le repli est l'automatisation de l'interface : pilotage
du logiciel Windows au clavier (AutoHotkey, ou un pilote UI Automation). Plus lent, plus
fragile aux mises à jour, mais sans risque pour l'intégrité de la base, puisque c'est
AnalysImmo lui-même qui écrit.

## Appareil XRF Fondis Electronic

L'analyseur portable photographié est un appareil de la gamme Fondis Electronic.
À vérifier avant de coder le rapprochement des mesures CREP :

- l'appareil se connecte-t-il en USB à un PC, et avec quel logiciel constructeur ?
- ce logiciel exporte-t-il les tirs en CSV / XLS, avec pour chaque tir : numéro, date,
  heure, valeur en mg/cm², durée de mesure, éventuellement un libellé saisi sur l'appareil ?
- peut-on saisir un libellé ou un numéro de local directement sur l'appareil au moment du
  tir ? Si oui, le rapprochement avec la dictée devient trivial.

Le schéma `plomb-crep.json` est construit pour ce rapprochement : la dictée fournit
`numeros_mesure`, l'export fournit `valeurs_mg_cm2`, et le classement 0/1/2/3 est calculé
par règle à partir des deux. Aucune valeur numérique ne doit transiter par la voix.
