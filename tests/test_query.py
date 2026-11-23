import pytest

from resume_ai import store
from resume_ai.models import Diplome, Langue, Poste, ProfilCV
from resume_ai.query import (
    CritereCompetence,
    CritereFonction,
    CritereLangue,
    Requete,
    compiler,
    executer,
)
from resume_ai.taxonomy import NiveauDiplome, NiveauLangue


def requete(diplome_min=None, langues=(), competences=(), fonctions=(), verification=""):
    return Requete(
        niveau_diplome_min=diplome_min,
        langues=list(langues),
        competences=list(competences),
        fonctions=list(fonctions),
        question_verification=verification,
    )


def profil(niveau_diplome, niveau_anglais, postes=(), declarees=()):
    return ProfilCV(
        diplomes=[
            Diplome(
                intitule="Diplôme",
                niveau=niveau_diplome,
                domaine="Informatique",
                etablissement="",
                annee_obtention=None,
            )
        ],
        langues=[Langue(langue="Anglais", niveau=niveau_anglais)],
        postes=list(postes),
        competences_declarees=list(declarees),
    )


def poste(debut, fin, technologies=(), fonctions=()):
    return Poste(
        titre="Poste",
        organisation="Anonyme",
        description="",
        debut=debut,
        fin=fin,
        technologies=list(technologies),
        fonctions=list(fonctions),
    )


def poste_python(debut, fin):
    return poste(debut, fin, ["Python"])


@pytest.fixture
def connexion():
    cnx = store.ouvrir(":memory:")
    profils = {
        "retenu": profil(
            NiveauDiplome.MAITRISE, NiveauLangue.C1, [poste_python("2018-01", "2023-12")]
        ),
        "diplome_insuffisant": profil(
            NiveauDiplome.BACCALAUREAT,
            NiveauLangue.C1,
            [poste_python("2018-01", "2023-12")],
        ),
        "python_seulement_declare": profil(
            NiveauDiplome.MAITRISE, NiveauLangue.C1, declarees=["Python", "SQL"]
        ),
        "anglais_faible": profil(
            NiveauDiplome.MAITRISE, NiveauLangue.A2, [poste_python("2018-01", "2023-12")]
        ),
        "experience_courte": profil(
            NiveauDiplome.MAITRISE, NiveauLangue.C1, [poste_python("2021-01", "2023-12")]
        ),
        "agente_centre_appel": profil(
            NiveauDiplome.COLLEGIAL,
            NiveauLangue.B2,
            [poste("2019-01", "2023-12", [], ["Centre d'appel", "service à la clientèle"])],
        ),
        "adjointe_clientele": profil(
            NiveauDiplome.COLLEGIAL,
            NiveauLangue.B1,
            [poste("2019-01", "2023-12", [], ["service à la clientèle", "opérations"])],
        ),
    }
    for nom, contenu in profils.items():
        store.enregistrer(cnx, nom, "texte du CV", contenu)
    yield cnx
    cnx.close()


def sources(resultats):
    return {ligne["source"] for ligne in resultats}


def test_requete_complete(connexion):
    """« Maîtrise ou plus, anglais, 4 ans et plus de Python. »"""
    assert sources(
        executer(
            connexion,
            requete(
                diplome_min=NiveauDiplome.MAITRISE,
                langues=[CritereLangue(langue="anglais", niveau_min=NiveauLangue.B2)],
                competences=[
                    CritereCompetence(
                        noms=["Python"], mois_min=48, accepter_declaree=False
                    )
                ],
            ),
        )
    ) == {"retenu"}


def test_le_doctorat_passe_le_plancher_de_maitrise(connexion):
    store.enregistrer(
        connexion,
        "docteure",
        "texte",
        profil(
            NiveauDiplome.DOCTORAT, NiveauLangue.C1, [poste_python("2018-01", "2023-12")]
        ),
    )
    assert sources(
        executer(
            connexion,
            requete(
                diplome_min=NiveauDiplome.MAITRISE,
                langues=[CritereLangue(langue="anglais", niveau_min=NiveauLangue.B2)],
                competences=[
                    CritereCompetence(
                        noms=["python"], mois_min=48, accepter_declaree=False
                    )
                ],
            ),
        )
    ) == {"retenu", "docteure"}


def test_competence_declaree_acceptee_sans_duree(connexion):
    resultats = executer(
        connexion,
        requete(
            competences=[
                CritereCompetence(noms=["Python"], mois_min=0, accepter_declaree=True)
            ]
        ),
    )
    assert "python_seulement_declare" in sources(resultats)


def test_competence_declaree_exclue_si_poste_exige(connexion):
    resultats = executer(
        connexion,
        requete(
            competences=[
                CritereCompetence(noms=["Python"], mois_min=0, accepter_declaree=False)
            ]
        ),
    )
    assert "python_seulement_declare" not in sources(resultats)


def test_recherche_par_fonction(connexion):
    """Le cas qui ne renvoyait rien : un métier n'est pas une technologie."""
    assert sources(
        executer(
            connexion,
            requete(fonctions=[CritereFonction(noms=["centre d'appel"], mois_min=0)]),
        )
    ) == {"agente_centre_appel"}


def test_plusieurs_termes_elargissent_le_critere(connexion):
    """Deux étiquettes voisines pour la même réalité : « ou » entre les termes.

    C'est le cas qui échouait — un profil étiqueté « service à la clientèle »
    restait invisible à une recherche formulée « centre d'appel ».
    """
    etroit = executer(
        connexion, requete(fonctions=[CritereFonction(noms=["centre d'appel"], mois_min=0)])
    )
    large = executer(
        connexion,
        requete(
            fonctions=[
                CritereFonction(
                    noms=["centre d'appel", "service à la clientèle"], mois_min=0
                )
            ]
        ),
    )
    assert sources(etroit) == {"agente_centre_appel"}
    assert sources(large) == {"agente_centre_appel", "adjointe_clientele"}


def test_un_terme_vide_est_ignore(connexion):
    assert sources(
        executer(
            connexion,
            requete(
                fonctions=[
                    CritereFonction(noms=["", "  ", "centre d'appel"], mois_min=0)
                ]
            ),
        )
    ) == {"agente_centre_appel"}


def test_un_critere_sans_terme_exploitable_est_ignore(connexion):
    """Le critère disparaît au lieu de produire un SQL invalide."""
    sql, parametres = compiler(
        requete(fonctions=[CritereFonction(noms=["", " "], mois_min=0)])
    )
    assert "where" not in sql
    assert parametres == []


def test_fonction_avec_duree_minimale(connexion):
    trouve = executer(
        connexion,
        requete(fonctions=[CritereFonction(noms=["centre d'appel"], mois_min=48)]),
    )
    trop_long = executer(
        connexion,
        requete(fonctions=[CritereFonction(noms=["centre d'appel"], mois_min=120)]),
    )
    assert sources(trouve) == {"agente_centre_appel"}
    assert trop_long == []


def test_une_fonction_n_est_pas_cherchee_parmi_les_competences(connexion):
    """La dimension sépare bien les deux vocabulaires."""
    assert (
        executer(
            connexion,
            requete(
                competences=[
                    CritereCompetence(
                        noms=["centre d'appel"], mois_min=0, accepter_declaree=True
                    )
                ]
            ),
        )
        == []
    )


def test_requete_vide_retourne_tout(connexion):
    assert len(executer(connexion, requete())) == 7


def test_les_valeurs_ne_sont_jamais_concatenees_dans_le_sql():
    sql, parametres = compiler(
        requete(
            competences=[
                CritereCompetence(
                    noms=["python'; drop table cv; --"],
                    mois_min=0,
                    accepter_declaree=True,
                )
            ],
            fonctions=[
                CritereFonction(noms=["x'; drop table fonction; --"], mois_min=0)
            ],
        )
    )
    assert "drop table" not in sql.lower()
    assert sum("drop table" in str(p) for p in parametres) == 2
