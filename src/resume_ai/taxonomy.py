"""Normalisation des libellés en valeurs comparables d'un CV à l'autre.

C'est le coeur du système : un filtre « maîtrise ou plus » n'est juste que si
« maîtrise », « M.Sc. » et « Master 2 » tombent sur la même valeur ordonnée.
"""

import re
import unicodedata
from enum import Enum


class NiveauDiplome(str, Enum):
    SECONDAIRE = "secondaire"
    COLLEGIAL = "collegial"
    CERTIFICAT = "certificat"
    BACCALAUREAT = "baccalaureat"
    DESS = "dess"
    MAITRISE = "maitrise"
    DOCTORAT = "doctorat"


# Échelle trouée : insérer un niveau plus tard ne force pas à réindexer la base.
RANG_DIPLOME: dict[NiveauDiplome, int] = {
    NiveauDiplome.SECONDAIRE: 10,
    NiveauDiplome.COLLEGIAL: 20,
    NiveauDiplome.CERTIFICAT: 25,
    NiveauDiplome.BACCALAUREAT: 30,
    NiveauDiplome.DESS: 35,
    NiveauDiplome.MAITRISE: 40,
    NiveauDiplome.DOCTORAT: 50,
}


class NiveauLangue(str, Enum):
    A1 = "a1"
    A2 = "a2"
    B1 = "b1"
    B2 = "b2"
    C1 = "c1"
    C2 = "c2"
    NATIF = "natif"


RANG_LANGUE: dict[NiveauLangue, int] = {
    NiveauLangue.A1: 1,
    NiveauLangue.A2: 2,
    NiveauLangue.B1: 3,
    NiveauLangue.B2: 4,
    NiveauLangue.C1: 5,
    NiveauLangue.C2: 6,
    NiveauLangue.NATIF: 7,
}

# Le « diplôme d'ingénieur » français et les grandes écoles valent bac+5 : on les
# aligne sur la maîtrise, sans quoi ces profils disparaissent d'un filtre « maîtrise+ ».
_ALIAS_DIPLOME: dict[str, NiveauDiplome] = {
    "secondaire": NiveauDiplome.SECONDAIRE,
    "des": NiveauDiplome.SECONDAIRE,
    "dep": NiveauDiplome.SECONDAIRE,
    "high school": NiveauDiplome.SECONDAIRE,
    "collegial": NiveauDiplome.COLLEGIAL,
    "dec": NiveauDiplome.COLLEGIAL,
    "aec": NiveauDiplome.COLLEGIAL,
    "cegep": NiveauDiplome.COLLEGIAL,
    "bts": NiveauDiplome.COLLEGIAL,
    "dut": NiveauDiplome.COLLEGIAL,
    "certificat": NiveauDiplome.CERTIFICAT,
    "mineure": NiveauDiplome.CERTIFICAT,
    "baccalaureat": NiveauDiplome.BACCALAUREAT,
    "bac": NiveauDiplome.BACCALAUREAT,
    "licence": NiveauDiplome.BACCALAUREAT,
    "bachelor": NiveauDiplome.BACCALAUREAT,
    "bsc": NiveauDiplome.BACCALAUREAT,
    "beng": NiveauDiplome.BACCALAUREAT,
    "bing": NiveauDiplome.BACCALAUREAT,
    "dess": NiveauDiplome.DESS,
    "graduate diploma": NiveauDiplome.DESS,
    "maitrise": NiveauDiplome.MAITRISE,
    "master": NiveauDiplome.MAITRISE,
    "msc": NiveauDiplome.MAITRISE,
    "meng": NiveauDiplome.MAITRISE,
    "ming": NiveauDiplome.MAITRISE,
    "mba": NiveauDiplome.MAITRISE,
    "diplome d ingenieur": NiveauDiplome.MAITRISE,
    "ingenieur diplome": NiveauDiplome.MAITRISE,
    "doctorat": NiveauDiplome.DOCTORAT,
    "phd": NiveauDiplome.DOCTORAT,
    "doctorate": NiveauDiplome.DOCTORAT,
    "postdoctorat": NiveauDiplome.DOCTORAT,
}

_ALIAS_NIVEAU_LANGUE: dict[str, NiveauLangue] = {
    "a1": NiveauLangue.A1,
    "debutant": NiveauLangue.A1,
    "notions": NiveauLangue.A2,
    "a2": NiveauLangue.A2,
    "elementaire": NiveauLangue.A2,
    "b1": NiveauLangue.B1,
    "intermediaire": NiveauLangue.B1,
    "b2": NiveauLangue.B2,
    "avance": NiveauLangue.B2,
    "professionnel": NiveauLangue.B2,
    "c1": NiveauLangue.C1,
    "courant": NiveauLangue.C1,
    "fluent": NiveauLangue.C1,
    "c2": NiveauLangue.C2,
    "bilingue": NiveauLangue.C2,
    "natif": NiveauLangue.NATIF,
    "native": NiveauLangue.NATIF,
    "langue maternelle": NiveauLangue.NATIF,
    "maternelle": NiveauLangue.NATIF,
}

_ALIAS_LANGUE: dict[str, str] = {
    "francais": "fr",
    "french": "fr",
    "fr": "fr",
    "anglais": "en",
    "english": "en",
    "en": "en",
    "espagnol": "es",
    "spanish": "es",
    "es": "es",
    "allemand": "de",
    "german": "de",
    "de": "de",
    "italien": "it",
    "italian": "it",
    "it": "it",
    "portugais": "pt",
    "portuguese": "pt",
    "pt": "pt",
    "arabe": "ar",
    "arabic": "ar",
    "ar": "ar",
    "mandarin": "zh",
    "chinois": "zh",
    "zh": "zh",
}

# Amorce : les termes inconnus sont conservés tels quels et consultables via
# `resume-ai vocabulaire`, ce qui fait grandir cette table à partir du corpus réel.
_ALIAS_COMPETENCE: dict[str, str] = {
    "python3": "python",
    "python 3": "python",
    "py": "python",
    "js": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "postgres": "postgresql",
    "psql": "postgresql",
    "ms sql server": "sql server",
    "mssql": "sql server",
    "k8s": "kubernetes",
    "golang": "go",
    "c sharp": "c#",
    "csharp": "c#",
    "dotnet": ".net",
    ".net core": ".net",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tf": "tensorflow",
    "aws": "amazon web services",
    "gcp": "google cloud",
    "azure devops": "azure",
    "power bi": "powerbi",
}


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation en espaces.

    Les points sont retirés avant tout le reste pour que « M.Sc. » devienne
    « msc » plutôt que « m sc », sinon les sigles échappent aux alias.
    """
    texte = _sans_accents(texte).lower().replace(".", "")
    texte = re.sub(r"[^a-z0-9+#]+", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _chercher_alias(libelle: str, aliases: dict):
    normalise = _normaliser(libelle)
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalise):
            return aliases[alias]
    return None


def _alias_le_plus_eleve(libelle: str, aliases: dict, rangs: dict):
    """Retient le niveau le plus élevé parmi ceux que l'intitulé mentionne.

    « Maîtrise après baccalauréat » vaut maîtrise. Un filtre de recrutement doit
    privilégier le rappel : mieux vaut un profil à vérifier qu'un profil écarté.
    """
    normalise = _normaliser(libelle)
    trouves = [
        valeur
        for alias, valeur in aliases.items()
        if re.search(rf"\b{re.escape(alias)}\b", normalise)
    ]
    return max(trouves, key=rangs.__getitem__, default=None)


def niveau_diplome(libelle: str) -> NiveauDiplome | None:
    """Déduit le niveau à partir d'un intitulé libre. None si indéterminable."""
    return _alias_le_plus_eleve(libelle, _ALIAS_DIPLOME, RANG_DIPLOME)


def niveau_langue(libelle: str) -> NiveauLangue | None:
    return _alias_le_plus_eleve(libelle, _ALIAS_NIVEAU_LANGUE, RANG_LANGUE)


def code_langue(libelle: str) -> str:
    """Code ISO 639-1 si connu, sinon le libellé normalisé."""
    code = _chercher_alias(libelle, _ALIAS_LANGUE)
    return code if code else _normaliser(libelle)


def normaliser_competence(nom: str) -> str:
    """Forme canonique d'une technologie.

    Les points sont conservés : « node.js » et « .net » sont des noms, pas des sigles.
    """
    propre = _sans_accents(nom).lower().strip()
    propre = re.sub(r"[^a-z0-9+#.\- ]+", " ", propre)
    propre = re.sub(r"\s+", " ", propre).strip()
    propre = re.sub(r"[.\-\s]+$", "", propre)
    return _ALIAS_COMPETENCE.get(propre, propre)
