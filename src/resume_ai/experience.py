"""Calcul des mois d'expérience par terme (technologie, métier, secteur).

« 4 ans d'expérience en Python » n'est presque jamais écrit dans un CV : c'est une
valeur dérivée des dates des postes où le terme apparaît. Deux postes qui se
chevauchent ne donnent pas deux fois l'expérience, d'où la fusion des intervalles.
"""

import re
from datetime import date
from typing import Callable, Iterable, NamedTuple

from .models import Poste
from .taxonomy import normaliser_competence

_FORMAT_MOIS = re.compile(r"^(\d{4})-(\d{1,2})")


class ExperienceTerme(NamedTuple):
    mois: int
    nom_brut: str


def index_mois(valeur: str) -> int | None:
    """Convertit « AAAA-MM » en un index de mois absolu. None si illisible."""
    correspondance = _FORMAT_MOIS.match(valeur.strip()) if valeur else None
    if not correspondance:
        return None
    annee, mois = int(correspondance.group(1)), int(correspondance.group(2))
    if not 1 <= mois <= 12:
        return None
    return annee * 12 + (mois - 1)


def fusionner(intervalles: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    fusionnes: list[tuple[int, int]] = []
    for debut, fin in sorted(intervalles):
        # `+ 1` fusionne aussi les périodes contiguës : janvier-mars suivi
        # d'avril-juin est une expérience continue de six mois.
        if fusionnes and debut <= fusionnes[-1][1] + 1:
            precedent = fusionnes[-1]
            fusionnes[-1] = (precedent[0], max(precedent[1], fin))
        else:
            fusionnes.append((debut, fin))
    return fusionnes


def mois_couverts(intervalles: Iterable[tuple[int, int]]) -> int:
    return sum(fin - debut + 1 for debut, fin in fusionner(intervalles))


def experience_par_terme(
    postes: Iterable[Poste],
    termes: Callable[[Poste], list[str]] = lambda poste: poste.technologies,
    aujourdhui: date | None = None,
) -> dict[str, ExperienceTerme]:
    reference = aujourdhui or date.today()
    mois_courant = reference.year * 12 + (reference.month - 1)

    intervalles: dict[str, list[tuple[int, int]]] = {}
    bruts: dict[str, str] = {}

    for poste in postes:
        debut = index_mois(poste.debut)
        if debut is None:
            continue
        fin = index_mois(poste.fin) if poste.fin else mois_courant
        if fin is None or fin < debut:
            continue
        for terme in termes(poste):
            canonique = normaliser_competence(terme)
            if not canonique:
                continue
            intervalles.setdefault(canonique, []).append((debut, fin))
            bruts.setdefault(canonique, terme)

    return {
        nom: ExperienceTerme(mois_couverts(periodes), bruts[nom])
        for nom, periodes in intervalles.items()
    }
