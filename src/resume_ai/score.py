"""Couche de score locale, par-dessus le filtre SQL.

Le filtre ne sait comparer que des étiquettes : un poste étiqueté « service à la
clientèle » à l'ingestion reste invisible à une recherche « centre d'appel ».
Cette couche pose la question directement au texte du parcours et rend une
probabilité, ce qui fournit aussi l'ordre de pertinence que le SQL n'a pas.

Le modèle tourne localement, donc le texte des CV ne sort pas de la machine —
contrairement à l'extraction, qui passe par l'API de Google.
"""

import os
from functools import lru_cache

MODELE_DEFAUT = os.environ.get("RESUME_AI_MODELE_SCORE", "convaiinnovations/laya")
# Le point de contrôle racine est anglophone ; les CV sont en français.
VARIANTE_DEFAUT = os.environ.get("RESUME_AI_VARIANTE_SCORE", "multilingual")

# Environ 100 ms par profil sur processeur : au-delà, une recherche cesse d'être
# interactive. Le filtre SQL a déjà réduit le corpus, on ne score que le dessus.
PLAFOND_DEFAUT = 60

_IDENTIFIANT = "correspond"


class ScoreIndisponible(RuntimeError):
    pass


@lru_cache(maxsize=2)
def charger(modele: str = MODELE_DEFAUT, variante: str | None = VARIANTE_DEFAUT):
    """Charge l'agent une fois pour toutes. Le premier appel télécharge les poids."""
    try:
        import laya
    except ImportError as erreur:
        raise ScoreIndisponible(
            'couche de score absente : pip install -e ".[score]"'
        ) from erreur
    return laya.load(modele, subfolder=variante or None)


def parcours(postes: list[dict]) -> str:
    """Texte soumis au modèle : ce que la personne a fait, sans les étiquettes."""
    morceaux = []
    for poste in postes:
        ligne = poste.get("titre") or ""
        if poste.get("organisation"):
            ligne += f" — {poste['organisation']}"
        if poste.get("description"):
            ligne += f". {poste['description']}"
        if ligne.strip():
            morceaux.append(ligne.strip())
    return " ".join(morceaux)


def scorer(agent, parcours_par_cv: dict[int, str], question: str) -> dict[int, float]:
    """Probabilité, par CV, que le parcours réponde oui à la question.

    La formulation de la question est déterminante : demander « cette personne
    passe-t-elle des appels » note une superviseure de centre d'appel à 0,22,
    alors que « a-t-elle une expérience en centre d'appel, agente ou
    superviseure » la note à 0,91. C'est pourquoi la question est rédigée par le
    modèle génératif à la traduction, et non fabriquée ici par concaténation.
    """
    exploitables = {cv_id: texte for cv_id, texte in parcours_par_cv.items() if texte.strip()}
    if not exploitables or not question.strip():
        return {}

    questions = {_IDENTIFIANT: {"type": "noul", "instructions": question}}
    identifiants = list(exploitables)
    etats = [{"parcours": exploitables[cv_id]} for cv_id in identifiants]

    resultats = agent.predict_batch(etats, questions)
    return {
        cv_id: float(resultat["answers"][_IDENTIFIANT]["noul"])
        for cv_id, resultat in zip(identifiants, resultats)
    }
