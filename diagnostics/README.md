# Automatisation de la saisie des diagnostics immobiliers

Pré-remplissage des grilles AnalysImmo à partir d'une dictée terrain au micro-cravate.

## Contenu

| Fichier | Rôle |
|---|---|
| `protocole-dictee.md` | Comment dicter sur le terrain. **À lire en premier** : c'est de là que vient la fiabilité. |
| `prompts/extraction.md` | Prompt système + prompt utilisateur à coller dans Make.com, prompt de vocabulaire Whisper, liste des contrôles de validation |
| `integration-analysimmo.md` | Accès à la base SQL, méthode de cartographie par diff, règles de sécurité, notes sur l'appareil XRF Fondis |
| `schemas/amiante.json` | Repérage amiante — NF X46-020, listes A et B de l'annexe 13-9 CSP |
| `schemas/termites.json` | État termites — NF P03-201 |
| `schemas/plomb-crep.json` | CREP — NF X46-030 |
| `schemas/electricite.json` | État de l'installation électrique — NF C 16-600 |
| `schemas/gaz.json` | État de l'installation gaz — NF P45-500 |
| `schemas/dpe.json` | Relevé de terrain DPE — méthode 3CL-DPE 2021 |

## Principes de conception

Trois choix structurent tous les schémas.

**1. Le modèle transcrit, il ne diagnostique pas.** Tous les champs qui engagent la
responsabilité de l'opérateur certifié — classement CREP, conclusion termites, présence de
DGI, étiquette DPE — sont marqués « calculé par règle » ou « recalculé côté code ». Le LLM
les laisse à `null`. Une hallucination sur un état de conservation amiante ou une anomalie
gaz, c'est votre signature en bas du rapport.

**2. Énumérations fermées partout où la réglementation impose une liste.** Le modèle
choisit dans la liste, il n'écrit pas de texte libre. Ce qu'il ne sait pas classer part
dans `incertain: true` + `motif_incertitude`, ce qui force la relecture au lieu de produire
une valeur plausible mais fausse.

**3. Traçabilité intégrale.** Chaque entrée porte un `verbatim` — l'extrait littéral du
transcript qui l'a produite. Rien ne se perd : ce qui n'a pas pu être rattaché atterrit
dans `meta.verbatim_non_classe`. En cas de litige, vous remontez de la case du rapport à la
phrase prononcée sur place.

## Les six modules ne s'automatisent pas de la même façon

| Module | Nature du relevé | Mode d'usage |
|---|---|---|
| Amiante | Observation libre par local et composant | Dictée balisée — **meilleur candidat, à faire en premier** |
| Termites | Parcours par local et ouvrage bois | Dictée balisée |
| Plomb / CREP | UD + substrat + revêtement, mesures chiffrées | Dictée balisée **+ export XRF** pour les valeurs |
| Électricité | Liste fermée de points de contrôle | Checklist guidée, pas dictée libre |
| Gaz | Liste fermée de points de contrôle | Checklist guidée, pas dictée libre |
| DPE | Relevé métrique et descriptif | Dictée pour le descriptif ; le calcul 3CL reste dans AnalysImmo |

## Ordre de mise en œuvre conseillé

1. **Amiante seul**, de bout en bout, sur 5 vrais dossiers. Le plus verbeux, le plus
   répétitif, le plus rentable, le moins risqué à valider.
2. **Termites**, qui réutilise la même mécanique.
3. **CREP**, une fois l'export du Fondis qualifié.
4. **Électricité et gaz**, qui relèvent d'un autre produit (checklist vocale).
5. **DPE** en dernier : le plus de champs, le moins de gain par champ.

## Utilisation dans Make.com

1. **Déclencheur** — arrivée du fichier audio (Drive, Dropbox, webhook depuis le téléphone).
2. **Transcription** — module Whisper, avec le prompt de vocabulaire de
   `prompts/extraction.md` dans le paramètre `prompt`. Sans lui, « fibrociment » devient
   « fibro ciment » et l'extraction rate derrière.
3. **Extraction** — module IA en **sortie structurée**, schéma du module collé dans le
   champ prévu, température à 0, prompts de `prompts/extraction.md`.
4. **Validation** — les contrôles listés en fin de `prompts/extraction.md`. En code, jamais
   en IA.
5. **Stockage** — le JSON validé, le transcript et l'audio, dans un dossier par affaire.
6. **Relecture humaine** — obligatoire, avant toute injection.
7. **Injection AnalysImmo** — voir `integration-analysimmo.md`.

Les schémas sont volontairement **autonomes** (pas de `$ref` entre fichiers) pour pouvoir
être collés tels quels dans Make.com. Ils suivent la convention des sorties structurées
strictes : `additionalProperties: false`, tous les champs dans `required`, les champs
facultatifs typés nullables.

## Avertissement

Ces schémas sont construits à partir des normes et arrêtés applicables, mais **les libellés
et codes exacts doivent être recalés sur la version d'AnalysImmo installée** avant toute
mise en production. La méthode de cartographie par diff décrite dans
`integration-analysimmo.md` est faite pour ça.

Deux points à vérifier en priorité, parce que les valeurs codées y sont les plus
susceptibles d'avoir été simplifiées ici :

- les valeurs d'état de conservation amiante (`EP` / `AC` / `AC1` / `AC2`) selon liste A ou
  liste B ;
- la numérotation des points de contrôle électricité (B.1 à B.11) et gaz (rubriques A à D),
  laissée en champ texte libre exprès : il faut exporter la liste réelle depuis AnalysImmo
  et la figer en énumération.
