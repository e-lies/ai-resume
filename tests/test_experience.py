from datetime import date

from resume_ai.experience import experience_par_terme, index_mois, mois_couverts
from resume_ai.models import Poste


def poste(debut, fin, technologies=(), fonctions=()):
    return Poste(
        titre="Développeur",
        organisation="Anonyme",
        description="",
        debut=debut,
        fin=fin,
        technologies=list(technologies),
        fonctions=list(fonctions),
    )


def test_index_mois():
    assert index_mois("2020-02") - index_mois("2020-01") == 1
    assert index_mois("2021-01") - index_mois("2020-01") == 12
    assert index_mois("2020-13") is None
    assert index_mois("bientôt") is None


def test_mois_couverts_compte_les_bornes():
    assert mois_couverts([(index_mois("2020-01"), index_mois("2020-12"))]) == 12


def test_les_periodes_qui_se_chevauchent_ne_comptent_qu_une_fois():
    intervalles = [
        (index_mois("2020-01"), index_mois("2021-12")),
        (index_mois("2021-01"), index_mois("2022-12")),
    ]
    assert mois_couverts(intervalles) == 36


def test_les_periodes_contigues_se_fusionnent():
    intervalles = [
        (index_mois("2020-01"), index_mois("2020-03")),
        (index_mois("2020-04"), index_mois("2020-06")),
    ]
    assert mois_couverts(intervalles) == 6


def test_experience_agregee_par_technologie():
    postes = [
        poste("2018-01", "2019-12", ["Python", "Django"]),
        poste("2020-01", "2021-12", ["Python 3", "React"]),
    ]
    resultat = experience_par_terme(postes)
    assert resultat["python"].mois == 48
    assert resultat["django"].mois == 24
    assert resultat["react"].mois == 24


def test_experience_agregee_par_fonction():
    postes = [
        poste("2018-01", "2019-12", ["Python"], ["centre d'appel"]),
        poste("2020-01", "2021-12", ["Python"], ["Centre d'appel", "gestion d'équipe"]),
    ]
    resultat = experience_par_terme(postes, lambda p: p.fonctions)
    assert resultat["centre d appel"].mois == 48
    assert resultat["gestion d equipe"].mois == 24
    # Les deux dimensions sont comptées séparément.
    assert "python" not in resultat


def test_poste_en_cours_compte_jusqu_a_aujourdhui():
    postes = [poste("2024-01", None, ["Go"])]
    resultat = experience_par_terme(postes, aujourdhui=date(2024, 12, 1))
    assert resultat["go"].mois == 12


def test_poste_aux_dates_illisibles_est_ignore():
    postes = [poste("date inconnue", "2024-01", ["Rust"])]
    assert experience_par_terme(postes) == {}
