"""Appel du modèle pour transformer un CV en données structurées."""

import os

from google import genai

from .models import ProfilCV

MODELE_DEFAUT = os.environ.get("RESUME_AI_MODELE", "gemini-3.8-flash")

# Les consignes sont dans l'entrée plutôt que dans `system_instruction` : l'API
# Interactions les redemande à chaque appel de toute façon, il n'y a rien à gagner
# à les séparer.
CONSIGNES = """Tu extrais des données structurées d'un CV pour alimenter un moteur de recherche interne.

Règles :
- N'extrais aucune donnée identifiante (nom, courriel, téléphone, adresse, date de naissance). Le schéma n'en contient pas : ignore-les.
- Le champ `niveau` d'un diplôme suit une échelle ordonnée : secondaire < collegial < certificat < baccalaureat < dess < maitrise < doctorat. Un diplôme d'ingénieur (bac+5) et un MBA valent `maitrise`. Ne retiens que les diplômes obtenus, pas les formations en cours.
- `description` d'un poste : deux à quatre phrases sur ce que la personne y a fait — responsabilités, ampleur, réalisations concrètes. Reformule fidèlement le CV, n'invente rien, et n'y fais figurer le nom d'aucune personne, ni le candidat ni un tiers (collègue, gestionnaire, client). Chaîne vide si le CV ne dit rien du contenu du poste.
- `technologies` d'un poste : uniquement celles que le CV rattache explicitement à CE poste.
- `fonctions` d'un poste : le métier exercé, le secteur de l'employeur et le contexte de travail, en termes courants — « service à la clientèle », « centre d'appel », « gestion de projet », « santé », « médias », « fonction publique ». Deux à cinq termes suffisent. N'y mets aucune technologie : elles vont dans `technologies`.
- `competences_declarees` : les technologies citées hors de tout poste daté (sections « Compétences », « Outils »...). N'y répète pas celles déjà rattachées à un poste.
- Dates au format AAAA-MM. Si seule l'année est connue : AAAA-01 pour un début, AAAA-12 pour une fin. `fin` vaut null si le poste est en cours.
- Si une langue est citée sans niveau, déduis-le du reste du CV ; à défaut, indique b2.
- N'invente rien : un renseignement absent reste une chaîne vide ou null.

CV à traiter :
---
"""


def creer_client() -> genai.Client:
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise RuntimeError(
            "clé absente : définir GEMINI_API_KEY (voir .env.example)"
        )
    return genai.Client()


def extraire_profil(
    client: genai.Client, texte: str, modele: str = MODELE_DEFAUT
) -> ProfilCV:
    interaction = client.interactions.create(
        model=modele,
        input=CONSIGNES + texte,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ProfilCV.model_json_schema(),
        },
    )
    return ProfilCV.model_validate_json(interaction.output_text)
