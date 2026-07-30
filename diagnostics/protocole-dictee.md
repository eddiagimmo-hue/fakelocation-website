# Protocole de dictée terrain

Le gain de fiabilité vient d'ici, pas du modèle. Une dictée balisée fait passer
l'extraction de « à peu près » à « quasi déterministe ». Dix minutes d'habitude à prendre.

## Règles générales

- Commencer chaque visite par : **« Début de dossier, référence …, adresse …, module … »**
- Baliser chaque entrée par **« Nouvelle observation »** et la clore par **« Fin observation »**.
- Annoncer les photos à voix haute : **« Photo »** juste avant ou après le déclenchement,
  pour que l'horodatage se recale sur l'observation en cours.
- En cas d'erreur : dire **« Correction »** puis redicter le champ. L'extraction garde
  la dernière valeur et signale la correction.
- Terminer par **« Fin de dossier »**.

## Amiante

> « Nouvelle observation. Niveau : rez-de-chaussée. Local : cuisine. Liste B. Composant :
> conduit de fluide. Matériau : fibrociment. Présence repérée. Contrôle visuel. État de
> conservation : EP. Photo. Fin observation. »

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
