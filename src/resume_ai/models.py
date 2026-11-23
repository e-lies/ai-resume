"""Schéma d'extraction.

Aucun champ identifiant (nom, courriel, téléphone, adresse) : la base ne contient
que des données de qualification. Le fichier source reste le seul endroit où
figure l'identité du candidat, ce qui limite la surface exposée sous la Loi 25.
"""

from pydantic import BaseModel, Field

from .taxonomy import NiveauDiplome, NiveauLangue

# Incrémenter dès que le schéma d'extraction change : les CV enregistrés sous une
# version antérieure sont réextraits depuis le texte conservé en base.
VERSION_SCHEMA = 3


class Diplome(BaseModel):
    intitule: str = Field(description="Intitulé exact tel qu'écrit dans le CV")
    niveau: NiveauDiplome = Field(description="Niveau équivalent sur l'échelle normalisée")
    domaine: str = Field(description="Domaine d'étude, chaîne vide si absent")
    etablissement: str = Field(description="Établissement, chaîne vide si absent")
    annee_obtention: int | None = Field(description="Année d'obtention, null si absente")


class Langue(BaseModel):
    langue: str = Field(description="Nom de la langue tel qu'écrit dans le CV")
    niveau: NiveauLangue = Field(
        description="Niveau CECR équivalent. 'natif' pour une langue maternelle."
    )


class Poste(BaseModel):
    titre: str
    organisation: str = Field(description="Employeur, chaîne vide si absent")
    description: str = Field(
        description=(
            "Ce que la personne a fait dans ce poste, en deux à quatre phrases :"
            " responsabilités, ampleur (taille d'équipe, volume), réalisations."
            " Reformule d'après le CV sans rien inventer, et ne nomme jamais un tiers."
        )
    )
    debut: str = Field(description="Format AAAA-MM. Si seule l'année est connue, AAAA-01.")
    fin: str | None = Field(description="Format AAAA-MM, ou null si le poste est en cours")
    technologies: list[str] = Field(
        description="Technologies que le CV rattache explicitement à CE poste"
    )
    fonctions: list[str] = Field(
        description=(
            "Métier, secteur d'activité et contexte de travail de CE poste, en"
            " termes courants : « service à la clientèle », « centre d'appel »,"
            " « gestion de projet », « santé », « médias ». Pas de technologies ici."
        )
    )


class ProfilCV(BaseModel):
    diplomes: list[Diplome]
    langues: list[Langue]
    postes: list[Poste]
    competences_declarees: list[str] = Field(
        description="Technologies citées hors de tout poste daté (section Compétences)"
    )
