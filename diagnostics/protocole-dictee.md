# Protocole de dictée terrain

Le gain de fiabilité vient d'ici, pas du modèle. Une dictée balisée fait passer
l'extraction de « à peu près » à « quasi déterministe ». Dix minutes d'habitude à prendre.

## Conventions de l'opérateur

Ces conventions sont encodées dans les schémas. Elles ne se redisent pas à chaque fois,
il suffit de les respecter en dictant.

- **Repérage des murs** : le **mur A** est celui par lequel on entre dans le volume, puis
  on tourne **dans le sens des aiguilles d'une montre** — B, C, D. Chaque recoin ajoute une
  lettre (E, F…). On dit « mur C », jamais « mur nord ».
- **Volume** : un volume = une entrée de grille, même s'il cumule plusieurs usages.
  « Salle d'eau WC » se dicte comme un seul volume, pas deux.
- **Hauteur** : partie basse / partie moyenne / partie haute / plafond / sol.

## Règles générales

- Commencer chaque visite par : **« Début de dossier, référence …, adresse …, module … »**
- Baliser chaque entrée par **« Nouvelle observation »** et la clore par **« Fin observation »**.
- Annoncer les photos à voix haute : **« Photo »** juste avant ou après le déclenchement,
  pour que l'horodatage se recale sur l'observation en cours.
- En cas d'erreur : dire **« Correction »** puis redicter le champ. L'extraction garde
  la dernière valeur et signale la correction.
- Terminer par **« Fin de dossier »**.

## Descriptif des volumes — à dicter en premier

C'est le relevé qui alimente ensuite termites, amiante et plomb. Le principe : **on ne
dicte que ce qui sort de l'ordinaire.**

Deux familles de pièces, avec leurs valeurs par défaut (voir `defauts-volumes.json`) :

| | Murs | Plafond | Sol |
|---|---|---|---|
| **Pièce sèche** (entrée, séjour, chambres, dégagement) | plâtre peinture | plâtre peinture | parquet |
| **Pièce humide** (cuisine, salle de bain, salle d'eau, WC) | plâtre peinture | plâtre peinture | carrelage |

Le mot-clé **« standard »** applique ces valeurs sans que tu aies à les énumérer :

> « Nouveau volume. Chambre 1. Standard. Fenêtre en mur B, PVC, volet roulant PVC,
> garde-corps métal peinture. Porte en mur A, bois peinture des deux côtés.
> Fin volume. »

Quand ça sort de l'ordinaire, tu le dis, et ta parole écrase le défaut :

> « Nouveau volume. Séjour. Standard, sauf murs en toile de verre peinte.
> Fin volume. »

> « Nouveau volume. Cuisine. Standard, sauf faïence sur le mur C. Fin volume. »

Deux garde-fous :

- **Tout champ rempli par défaut est signalé en relecture** (`defauts_appliques`). Tu vois
  d'un coup d'œil ce que tu n'as pas réellement prononcé.
- **L'état de conservation des revêtements n'a jamais de valeur par défaut.** Il conditionne
  le classement CREP, il doit être constaté et dicté.

## Amiante

> « Nouvelle observation. Niveau : rez-de-chaussée. Volume : salle d'eau WC. Mur C, partie
> haute. Liste B. Composant : conduit de ventilation, débouché en façade. Matériau :
> fibrociment. Présence supposée. Contrôle visuel. État de conservation : EP. Deux mètres
> linéaires. Photo. Fin observation. »

Le **schéma de repérage** reste dessiné par l'opérateur. La dictée ne le produit pas, mais
comme chaque observation porte son volume, son mur et sa hauteur, l'extraction sort une
liste positionnée (« salle d'eau WC → OBS-003, mur C, partie haute ») qui se reporte
mécaniquement sur le croquis. C'est du report, plus de la reconstitution de mémoire.

Si prélèvement :

> « … Prélèvement référence A-03, matériau présumé enduit. Fin observation. »

Si local sans matériau :

> « Nouvelle observation. Local : chambre 1. Aucun matériau de la liste. Fin observation. »

## Termites

> « Nouvelle observation. Niveau : sous-sol. Local : cave. Ouvrage : solive. Bois feuillu.
> Sondage réalisé. Résultat : présence d'indices. Indices : galeries et cordonnets.
> Autres agents : aucun. État : dégradé. Photo. Fin observation. »

Pour un local sain, la forme courte suffit :

> « Nouvelle observation. Local : salon. Ouvrage : plinthe. Sondage réalisé. Absence
> d'indice. Fin observation. »

## Plomb / CREP

Les valeurs de mesure ne se dictent pas : elles viennent de l'export de l'appareil.
Ce qui se dicte, c'est l'unité de diagnostic et le **numéro de tir**.

> « Nouvelle observation. Local : chambre 2. Zone : mur nord. Unité de diagnostic : mur
> peint. Substrat : plâtre. Revêtement : peinture. Mesure directe, tir 1042. État du
> revêtement : état d'usage. Fin observation. »

## Électricité et gaz — checklist, pas dictée libre

Ces deux modules suivent une liste fermée de points de contrôle. Le bon format est
question/réponse, l'application annonçant le point :

> App : « B.3.3.1 — protection contre les surintensités adaptée à la section des conducteurs ? »
> Vous : « Anomalie. Localisation : tableau du garage. Observation : fusible de 32 ampères
> sur du 1,5 carré. Photo. »

ou simplement « Conforme », « Sans objet », « Non vérifiable, tableau inaccessible ».

Pour le gaz, la réponse est le code : « A2, raccordement de la cuisinière par tuyau souple
périmé » ou « DGI, fuite sur l'organe de coupure ».

## DPE

Dictée par élément d'enveloppe puis par système :

> « Nouvelle observation. Mur : façade sud. Surface : 24 mètres carrés. Matériau : bloc
> béton creux. Épaisseur : 20 centimètres. Isolation intérieure, laine de verre,
> 10 centimètres, année 2005, justificatif facture. Fin observation. »

> « Nouvelle observation. Chauffage : chaudière à condensation, gaz naturel, marque
> Saunier Duval, année 2018, 24 kilowatts, émetteurs radiateurs basse température,
> régulation thermostat d'ambiance, distribution isolée. Photo de la plaque
> signalétique. Fin observation. »

## RGPD

Le micro tourne en continu : il capte la voix des occupants. Deux règles simples :

- prévenir l'occupant que vous enregistrez vos observations et couper pendant les
  échanges qui ne sont pas des constats ;
- purger les enregistrements audio à échéance fixe (par ex. 90 jours après émission du
  rapport), en conservant le transcript et le JSON qui, eux, servent de traçabilité.
