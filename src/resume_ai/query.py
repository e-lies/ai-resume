"""Traduction d'une question en langage naturel vers un filtre SQL.

Le modèle ne produit jamais de SQL : il remplit une structure validée, qui est
ensuite compilée en requête paramétrée. Aucune valeur issue du modèle n'atteint
la chaîne SQL, et un champ inventé fait échouer la validation Pydantic.
"""

import sqlite3

from google import genai
from pydantic import BaseModel

from .extraction import MODELE_DEFAUT
from .taxonomy import (
    RANG_DIPLOME,
    RANG_LANGUE,
    NiveauDiplome,
    NiveauLangue,
    code_langue,
    normaliser_competence,
)


# Nombre de termes du corpus soumis au modèle pour qu'il y rattache la question.
# Mesuré sur 3 000 CV synthétiques : environ 600 technologies et 400 fonctions
# distinctes, soit ~2 500 jetons — négligeable. Ce plafond cesse de convenir bien
# avant de coûter cher : au-delà d'un millier de termes, choisir le bon dans une
# liste devient l'exploit, et il faudra présélectionner par proximité vectorielle.
VOCABULAIRE_MAX = 800


class CritereLangue(BaseModel):
    langue: str
    niveau_min: NiveauLangue


class CritereCompetence(BaseModel):
    noms: list[str]
    mois_min: int
    accepter_declaree: bool


class CritereFonction(BaseModel):
    noms: list[str]
    mois_min: int


class Requete(BaseModel):
    niveau_diplome_min: NiveauDiplome | None
    langues: list[CritereLangue]
    competences: list[CritereCompetence]
    fonctions: list[CritereFonction]
    question_verification: str


CONSIGNES = """Tu traduis une demande de recrutement en filtre structuré.

Échelle des diplômes, ordonnée : secondaire < collegial < certificat < baccalaureat < dess < maitrise < doctorat.
Niveaux de langue, ordonnés : a1 < a2 < b1 < b2 < c1 < c2 < natif.

Deux dimensions distinctes, à ne pas confondre :
- `competences` : technologies, outils, logiciels, langages de programmation. Par exemple python, sql server, powerbi.
- `fonctions` : métier, secteur d'activité, contexte de travail. Par exemple centre d'appel, service à la clientèle, gestion de projet, santé, médias. Une demande du type « expérience en centre d'appel » relève des fonctions, jamais des compétences.

Règles :
- `niveau_diplome_min` est un plancher : « au moins une maîtrise » donne `maitrise`. null si la demande ne parle pas de diplôme.
- « parler une langue » sans précision de niveau correspond à b2.
- `mois_min` s'exprime en MOIS : « 4 ans ou plus » donne 48. 0 si aucune durée n'est exigée.
- `accepter_declaree` vaut true si la technologie peut simplement figurer dans la liste de compétences du CV, false si elle doit être adossée à un poste daté. Mets false dès qu'une durée est exigée.
- `noms` est une LISTE. Propose tous les termes du vocabulaire qui désignent la même activité que la demande, pas seulement le meilleur : un profil est retenu dès qu'il en porte un seul. Si la demande dit « call center » et que le corpus contient « centre d appel », « service a la clientele » et « relation client », donne les trois.
- N'y mets que des termes qui désignent la même ACTIVITÉ, jamais le domaine qui l'entoure : « soins infirmiers » ne doit pas entraîner « santé », ni « soudure » entraîner « industrie ». Un secteur n'est pas un métier.
- Quand aucun terme du corpus ne convient, reprends celui de la demande — zéro résultat vaut mieux qu'un résultat faux.
- `question_verification` reformule la demande en UNE question fermée, posée au parcours professionnel d'une personne, à laquelle on répond par oui ou non. Elle sert ensuite à classer les profils retenus. Commence-la par « Le parcours décrit-il ». Rédige-la de façon INCLUSIVE quant au rôle et au niveau : « Le parcours décrit-il une expérience en centre d'appel ou en relation client par téléphone, que la personne soit agente ou superviseure ? » plutôt que « passe-t-elle des appels ? », sans quoi un profil d'encadrement est écarté à tort.

Vocabulaire des compétences : {competences}

Vocabulaire des fonctions : {fonctions}

Demande : {question}
"""


def _termes(noms: list[str]) -> list[str]:
    """Formes canoniques, dédoublonnées, en préservant l'ordre proposé."""
    vus: dict[str, None] = {}
    for nom in noms:
        canonique = normaliser_competence(nom)
        if canonique:
            vus.setdefault(canonique, None)
    return list(vus)


def _appartenance(table: str, termes: list[str]) -> str:
    return f"{table}.nom in ({','.join('?' * len(termes))})"


def compiler(requete: Requete) -> tuple[str, list]:
    clauses: list[str] = []
    parametres: list = []

    if requete.niveau_diplome_min is not None:
        clauses.append("cv.niveau_diplome_max >= ?")
        parametres.append(RANG_DIPLOME[requete.niveau_diplome_min])

    for critere in requete.langues:
        clauses.append(
            "exists (select 1 from langue"
            " where langue.cv_id = cv.id and langue.code = ? and langue.rang >= ?)"
        )
        parametres += [code_langue(critere.langue), RANG_LANGUE[critere.niveau_min]]

    for critere in requete.competences:
        termes = _termes(critere.noms)
        if not termes:
            continue
        conditions = ["competence.cv_id = cv.id", _appartenance("competence", termes)]
        parametres += termes
        if critere.mois_min > 0:
            conditions.append("competence.mois >= ?")
            parametres.append(critere.mois_min)
        if not critere.accepter_declaree:
            conditions.append("competence.source = 'poste'")
        clauses.append(
            f"exists (select 1 from competence where {' and '.join(conditions)})"
        )

    for critere in requete.fonctions:
        termes = _termes(critere.noms)
        if not termes:
            continue
        conditions = ["fonction.cv_id = cv.id", _appartenance("fonction", termes)]
        parametres += termes
        if critere.mois_min > 0:
            conditions.append("fonction.mois >= ?")
            parametres.append(critere.mois_min)
        clauses.append(
            f"exists (select 1 from fonction where {' and '.join(conditions)})"
        )

    sql = "select cv.id, cv.source, cv.niveau_diplome_max from cv"
    if clauses:
        sql += " where " + " and ".join(clauses)
    return sql + " order by cv.id", parametres


def executer(connexion: sqlite3.Connection, requete: Requete) -> list[sqlite3.Row]:
    sql, parametres = compiler(requete)
    return list(connexion.execute(sql, parametres))


def traduire(
    client: genai.Client,
    question: str,
    vocabulaire_competences: list[str],
    vocabulaire_fonctions: list[str],
    modele: str = MODELE_DEFAUT,
) -> Requete:
    interaction = client.interactions.create(
        model=modele,
        input=CONSIGNES.format(
            competences=", ".join(vocabulaire_competences) or "(vide)",
            fonctions=", ".join(vocabulaire_fonctions) or "(vide)",
            question=question,
        ),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": Requete.model_json_schema(),
        },
    )
    return Requete.model_validate_json(interaction.output_text)


def _duree(mois: int) -> str:
    return f", au moins {mois} mois ({mois / 12:.1f} ans)"


def criteres_lisibles(requete: Requete) -> list[str]:
    """Rend lisibles les critères interprétés, pour que l'utilisateur puisse corriger."""
    lignes = []
    if requete.niveau_diplome_min is not None:
        lignes.append(f"diplôme : {requete.niveau_diplome_min.value} ou plus")
    for critere in requete.langues:
        lignes.append(
            f"langue : {code_langue(critere.langue)} niveau {critere.niveau_min.value} ou plus"
        )
    for critere in requete.competences:
        detail = f"compétence : {' ou '.join(_termes(critere.noms))}"
        if critere.mois_min:
            detail += _duree(critere.mois_min)
        if not critere.accepter_declaree:
            detail += ", adossée à un poste daté"
        lignes.append(detail)
    for critere in requete.fonctions:
        detail = f"fonction : {' ou '.join(_termes(critere.noms))}"
        if critere.mois_min:
            detail += _duree(critere.mois_min)
        lignes.append(detail)
    return lignes


def resumer(requete: Requete) -> str:
    lignes = criteres_lisibles(requete)
    return "\n".join(f"  - {l}" for l in lignes) or "  (aucun critère)"
