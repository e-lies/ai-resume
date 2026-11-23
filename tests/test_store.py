import sqlite3

import pytest

from resume_ai import store
from resume_ai.models import VERSION_SCHEMA, Diplome, Langue, Poste, ProfilCV
from resume_ai.taxonomy import NiveauDiplome, NiveauLangue


def profil(description="Supervision d'une équipe de douze agents."):
    return ProfilCV(
        diplomes=[
            Diplome(
                intitule="Baccalauréat",
                niveau=NiveauDiplome.BACCALAUREAT,
                domaine="Communication",
                etablissement="",
                annee_obtention=2017,
            )
        ],
        langues=[Langue(langue="Anglais", niveau=NiveauLangue.C1)],
        postes=[
            Poste(
                titre="Superviseure",
                organisation="Anonyme",
                description=description,
                debut="2021-01",
                fin=None,
                technologies=["Genesys"],
                fonctions=["centre d'appel"],
            )
        ],
        competences_declarees=[],
    )


@pytest.fixture
def connexion():
    cnx = store.ouvrir(":memory:")
    yield cnx
    cnx.close()


def test_la_description_du_poste_est_conservee(connexion):
    store.enregistrer(connexion, "cv-1", "texte", profil())
    cv_id = connexion.execute("select id from cv").fetchone()["id"]
    postes = store.detailler(connexion, [cv_id])[cv_id]["postes"]
    assert postes[0]["description"] == "Supervision d'une équipe de douze agents."


def test_une_reextraction_conserve_l_identifiant_et_les_notes(connexion):
    """Invariant central : réextraire n'est pas supprimer.

    Les notes sont en cascade sur `cv.id` ; si `enregistrer` recréait la ligne au
    lieu de la mettre à jour, toute évolution du schéma les effacerait.
    """
    cv_id = store.enregistrer(connexion, "cv-1", "texte", profil())
    store.ajouter_note(connexion, cv_id, "IS", "Entrevue concluante.")

    reextrait = store.enregistrer(connexion, "cv-1", "texte", profil("Réextraite."))

    assert reextrait == cv_id
    assert connexion.execute("select count(*) as n from cv").fetchone()["n"] == 1
    notes = store.notes(connexion, [cv_id])[cv_id]
    assert len(notes) == 1
    assert notes[0]["contenu"] == "Entrevue concluante."

    postes = store.detailler(connexion, [cv_id])[cv_id]["postes"]
    assert len(postes) == 1, "les tables dérivées ne doivent pas s'accumuler"
    assert postes[0]["description"] == "Réextraite."


def test_supprimer_un_cv_supprime_ses_notes(connexion):
    cv_id = store.enregistrer(connexion, "cv-1", "texte", profil())
    store.ajouter_note(connexion, cv_id, "IS", "Entrevue concluante.")

    store.supprimer(connexion, [cv_id])

    assert connexion.execute("select count(*) as n from note").fetchone()["n"] == 0


def test_une_note_porte_son_auteur_et_sa_date(connexion):
    cv_id = store.enregistrer(connexion, "cv-1", "texte", profil())
    store.ajouter_note(connexion, cv_id, "IS", "Vu sur LinkedIn : parle espagnol.")
    note = store.notes(connexion, [cv_id])[cv_id][0]
    assert note["auteur"] == "IS"
    assert note["cree_le"].startswith("20")


def test_suppression_d_une_note(connexion):
    cv_id = store.enregistrer(connexion, "cv-1", "texte", profil())
    note_id = store.ajouter_note(connexion, cv_id, "IS", "À supprimer.")
    assert store.supprimer_note(connexion, note_id) == 1
    assert store.notes(connexion, [cv_id])[cv_id] == []
    assert store.supprimer_note(connexion, note_id) == 0


def test_ouverture_d_une_base_dont_la_table_note_est_ancienne(tmp_path):
    """Une base créée avant le passage de `note.source` à `note.cv_id`.

    Sans migration, `ouvrir` échouait dès l'index : « no such column: cv_id ».
    """
    chemin = tmp_path / "ancienne.db"
    brut = sqlite3.connect(chemin)
    brut.executescript(
        """
        create table cv (
            id integer primary key autoincrement,
            source text not null unique,
            extrait_le text not null,
            texte text not null,
            profil_json text not null,
            niveau_diplome_max integer not null
        );
        create table note (
            id integer primary key autoincrement,
            source text not null,
            cree_le text not null,
            auteur text not null,
            contenu text not null
        );
        insert into cv (source, extrait_le, texte, profil_json, niveau_diplome_max)
        values ('corpus/a.pdf', '2026-01-01', 'texte', '{}', 30);
        insert into note (source, cree_le, auteur, contenu)
        values ('corpus/a.pdf', '2026-01-02', 'IS', 'Note à conserver.');
        insert into note (source, cree_le, auteur, contenu)
        values ('corpus/disparu.pdf', '2026-01-02', 'IS', 'CV absent.');
        """
    )
    brut.commit()
    brut.close()

    connexion = store.ouvrir(chemin)
    cv_id = connexion.execute("select id from cv").fetchone()["id"]
    reprises = store.notes(connexion, [cv_id])[cv_id]
    assert [n["contenu"] for n in reprises] == ["Note à conserver."]
    assert connexion.execute("select count(*) as n from note").fetchone()["n"] == 1
    connexion.close()


def test_detection_des_cv_au_format_anterieur(connexion):
    store.enregistrer(connexion, "cv-1", "texte", profil())
    assert store.obsoletes(connexion) == []

    connexion.execute("update cv set version_schema = ?", (VERSION_SCHEMA - 1,))
    obsoletes = store.obsoletes(connexion)
    assert [ligne["source"] for ligne in obsoletes] == ["cv-1"]
    assert obsoletes[0]["texte"] == "texte"
