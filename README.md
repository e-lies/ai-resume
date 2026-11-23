# resume-ai

Recherche en langage naturel dans une base de CV (PDF, Word, texte).

Exemple : « tous les profils avec un diplôme d'au moins niveau maîtrise, sachant
parler anglais et ayant 4 ans ou plus d'expérience en Python. »

## Comment ça marche

L'essentiel du travail est fait une fois, à l'ingestion, pas à la recherche.

1. **Lecture** — le fichier est converti en texte (`pdfplumber`, `python-docx`).
2. **Extraction** — un modèle Gemini remplit un schéma JSON strict : diplômes avec
   niveau normalisé, langues avec niveau CECR, postes datés avec une **description**
   de ce que la personne y a fait, et pour chaque poste deux dimensions distinctes —
   les **technologies** employées et les **fonctions** (métier, secteur, contexte
   de travail : « centre d'appel », « santé »).
3. **Normalisation** — « M.Sc. », « Master 2 » et « maîtrise » tombent sur la même
   valeur ordonnée ; les mois d'expérience par technologie sont *calculés* à partir
   des dates de postes, les périodes qui se chevauchent n'étant comptées qu'une fois.
4. **Stockage** — SQLite. Le texte brut et le JSON d'extraction sont conservés, ce
   qui permet de réextraire après une évolution du schéma sans relire les fichiers.
5. **Recherche** — la question est traduite en une structure validée, puis compilée
   en SQL paramétré. Le modèle ne produit jamais de SQL.

## Installation

```bash
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Copiez `.env.example` et renseignez `GEMINI_API_KEY` dans votre environnement.

## Interface web

Deux serveurs, dans deux terminaux. L'API d'abord :

```bash
.\serveur.ps1
```

Passez par ce script plutôt que d'appeler `uvicorn` directement. Lancé avec le
Python système au lieu de celui de `.venv`, uvicorn réserve le port puis échoue
silencieusement à l'import : le serveur écoute sans jamais répondre, et les
requêtes expirent sans message d'erreur.

Puis le front, qui relaie `/api` vers le premier — il n'y a donc pas de CORS à
gérer :

```bash
npm --prefix web install
```

```bash
npm --prefix web run dev
```

L'interface s'ouvre sur `http://localhost:5173`. On y dépose des fichiers par
glisser-déposer (trois extractions menées de front), et la recherche affiche
d'abord les critères tels qu'elle les a compris, puis les profils retenus. Sans
recherche en cours, la liste montre l'ensemble du corpus.

## Utilisation en ligne de commande

```bash
.venv\Scripts\python.exe -m resume_ai.cli ingerer samples
```

```bash
.venv\Scripts\python.exe -m resume_ai.cli chercher "profils avec au moins une maitrise, anglais, 4 ans d'experience en Python"
```

```bash
.venv\Scripts\python.exe -m resume_ai.cli vocabulaire --dimension fonction
```

Après une évolution du schéma d'extraction, les CV déjà en base sont réextraits
depuis le texte conservé, sans relire ni reparser les fichiers d'origine :

```bash
.venv\Scripts\python.exe -m resume_ai.cli reextraire
```

Ajoutez `--supprimer` pour effacer ces entrées plutôt que les mettre à jour.
Attention : réextraire renvoie le texte des CV au modèle, ce qui est un
traitement de renseignements personnels à autoriser sciemment.

`chercher` affiche toujours les critères tels qu'il les a compris avant de donner
les résultats : c'est le seul moyen de repérer une question mal interprétée.
`vocabulaire` liste les technologies extraites par fréquence — c'est de là que
doit grandir la table d'alias de `taxonomy.py`, à partir du corpus réel.

## Choix de conception

**Aucune donnée identifiante en base.** Le schéma d'extraction ne contient ni nom,
ni courriel, ni téléphone, ni adresse. La base ne stocke que des données de
qualification ; le fichier source reste le seul endroit où figure l'identité.

**Compétence déclarée ≠ expérience mesurée.** Une technologie listée dans une
section « Compétences » sans rattachement à un poste daté est enregistrée avec
zéro mois. Un filtre « 4 ans de Python » l'écarte donc, un filtre « connaît
Python » la retient.

**Le rappel prime sur la précision.** Un intitulé mentionnant plusieurs niveaux
est ramené au plus élevé. Mieux vaut un profil à vérifier qu'un bon profil écarté.

**Technologies et fonctions sont deux dimensions séparées.** Un centre d'appel
n'est pas une technologie : sans cette séparation, une recherche par métier
n'avait nulle part où aller et ne renvoyait jamais rien, quelle que soit
l'orthographe employée.

**Réextraire n'est pas supprimer.** Les notes sont en cascade sur `cv.id` :
supprimer un CV supprime ses notes, ce qui est le comportement voulu. Mais
`enregistrer` met la ligne `cv` à jour au lieu de la recréer, et ne reconstruit
que les tables dérivées — sans quoi chaque évolution du schéma d'extraction
effacerait des notes, seule donnée du système qu'on ne peut pas régénérer. Un
test verrouille cet invariant. Chaque note porte son auteur et sa date, parce
qu'un candidat peut en demander l'accès ou la rectification.

**La synonymie se résout à la traduction de la question, sur plusieurs termes.**
Le modèle reçoit le vocabulaire réel du corpus et propose *tous* les termes qui
désignent la même activité : « call center » devient « centre d'appel ou service
à la clientèle », et un profil est retenu dès qu'il en porte un. Sans cela, un
poste étiqueté « service à la clientèle » à l'ingestion restait invisible à une
recherche formulée « centre d'appel » — les deux côtés étiquettent
indépendamment et la jointure est une égalité de chaînes.

La contrepartie est la précision, tenue par une règle : un terme n'est ajouté
que s'il désigne la même *activité*, jamais le domaine qui l'entoure. « Soins
infirmiers » n'entraîne donc pas « santé ». L'interface affiche toujours les
termes retenus, ce qui rend un élargissement abusif visible.

Limite connue : avec plusieurs termes, une durée minimale s'applique à chacun
séparément — il faut qu'un seul terme atteigne le seuil. Les mois ne
s'additionnent pas entre synonymes, faute de quoi des périodes qui se
chevauchent seraient comptées deux fois.

## Coût

Pour 3 000 CV, en ordre de grandeur (environ 4 000 jetons en entrée et 800 en
sortie par CV) :

| Modèle                  | Coût total approximatif |
| ----------------------- | ----------------------- |
| `gemini-3.8-flash`      | ~18 $ US                |
| `gemini-3.1-flash-lite` | ~7 $ US                 |

À ce volume, le coût n'est pas le facteur décisif : c'est la qualité d'extraction
qui l'est. Constituez un échantillon de référence annoté à la main avant de
choisir, et mesurez plutôt que d'estimer.

## Limites connues

- Les PDF numérisés ne sont pas traités : il faudrait une passe OCR.
- Le format `.doc` (ancien Word) doit être converti en `.docx` au préalable.
- La couche sémantique (recherche vectorielle pour les critères flous et pour
  rattraper ce que l'extraction a manqué) n'est pas implémentée.
- La chaîne complète a été vérifiée sur des fichiers `.txt` uniquement. La
  lecture des PDF et des `.docx` n'a pas encore été éprouvée sur de vrais CV.
- Le dépôt par glisser-déposer n'a été validé qu'au travers de l'API ; le
  comportement du navigateur lui-même reste à confirmer à la main.
- L'API n'a aucune authentification et le téléversement traite un fichier par
  requête HTTP. Cela convient jusqu'à quelques centaines de CV ; au-delà il
  faudra une file d'attente et un suivi d'avancement côté serveur.
- L'interface n'affiche pas encore le vocabulaire extrait, disponible seulement
  en ligne de commande et sur `GET /api/vocabulaire`.
- Un poste ne peut porter qu'une seule période continue. Un emploi saisonnier
  décrit comme « été 2015 et été 2016 » est donc compté comme une période unique,
  et la durée est surévaluée.
- Le rattachement au vocabulaire du corpus est binaire : ou bien le modèle juge
  les termes équivalents, ou bien il n'associe rien. « Télémarketing » ne ramène
  donc pas les profils de centre d'appel. Une couche vectorielle donnerait une
  proximité graduée plutôt que ce tout ou rien ; c'est l'étape suivante.

## Classement par pertinence

Le filtre SQL rend un ensemble, pas un ordre : sur un grand corpus, une requête
large renvoie des centaines de profils triés par identifiant. Une couche de score
optionnelle pose une question fermée directement au parcours de chaque profil
retenu et rend une probabilité, qui sert d'ordre.

```bash
.venv\Scripts\python.exe -m pip install -e ".[score]"
```

Elle s'appuie sur Laya, un modèle de décision non autorégressif qui ne génère pas
de texte : on lui donne un état et une question typée, il rend une probabilité
calibrée. Il **tourne localement**, donc le texte des CV ne sort pas de la
machine — contrairement à l'extraction, qui passe par l'API de Google. Comptez
environ 650 Mo de poids au premier appel et 100 ms par profil sur processeur.

La formulation de la question est déterminante, et c'est le modèle génératif qui
la rédige au moment de traduire la demande. Mesuré sur les profils d'exemple :
demander « cette personne passe-t-elle des appels » note une superviseure de
centre d'appel à 0,22, alors que « a-t-elle une expérience en centre d'appel,
agente ou superviseure » la note à 0,91. La consigne impose donc une formulation
inclusive quant au rôle.

Le classement est facultatif à chaque recherche, et borné aux soixante premiers
résultats. Au-delà, la recherche cesserait d'être interactive.

Réserve : cette couche n'a été éprouvée que sur les profils fictifs de
`samples/`, avec une séparation nette — positifs au-dessus de 0,77, négatifs
sous 0,28. Rien ne dit qu'elle tiendra sur un corpus réel tant qu'un échantillon
annoté ne l'aura pas mesuré.

## Notes sur un candidat

Chaque fiche permet d'ajouter des notes — une observation tirée d'un profil
public, un compte rendu d'entrevue. Elles survivent aux réextractions.

Ce sont des renseignements personnels au même titre que le CV, et davantage
exposés : ils sont subjectifs et le candidat a le droit d'en demander l'accès et
la rectification. D'où l'auteur et la date obligatoires sur chaque note. Une note
recueillie sur un profil public reste une collecte auprès d'un tiers, avec ses
propres obligations d'information — à valider avec votre responsable de la
protection des renseignements personnels avant toute mise en service.

## Vie privée

Des CV sont des renseignements personnels au sens de la Loi 25. Avant toute mise
en service, il faut valider l'hébergement et le fournisseur du modèle, le contrôle
d'accès, la durée de conservation et la journalisation des consultations. Le
dossier `corpus/` est exclu du dépôt par `.gitignore` ; les fichiers de `samples/`
sont fictifs.

## Tests

```bash
.venv\Scripts\python.exe -m pytest
```

Les tests couvrent la normalisation, le calcul d'expérience et la compilation des
requêtes — tout ce qui ne dépend pas d'un appel réseau.
