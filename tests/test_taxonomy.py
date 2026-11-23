from resume_ai.taxonomy import (
    NiveauDiplome,
    NiveauLangue,
    code_langue,
    niveau_diplome,
    niveau_langue,
    normaliser_competence,
)


def test_equivalences_de_maitrise():
    for libelle in [
        "Maîtrise en informatique",
        "M.Sc. Computer Science",
        "Master 2 Données",
        "MBA",
        "Diplôme d'ingénieur, INSA Lyon",
    ]:
        assert niveau_diplome(libelle) is NiveauDiplome.MAITRISE, libelle


def test_niveaux_inferieurs_distincts():
    assert niveau_diplome("DEC en techniques informatiques") is NiveauDiplome.COLLEGIAL
    assert niveau_diplome("Baccalauréat en génie logiciel") is NiveauDiplome.BACCALAUREAT
    assert niveau_diplome("Licence de mathématiques") is NiveauDiplome.BACCALAUREAT
    assert niveau_diplome("Ph.D. in Statistics") is NiveauDiplome.DOCTORAT
    assert niveau_diplome("Formation Excel de trois jours") is None


def test_le_bac_ne_supplante_pas_la_maitrise():
    # « baccalauréat » contient « bac » : l'alias le plus long doit gagner.
    assert niveau_diplome("Baccalauréat") is NiveauDiplome.BACCALAUREAT
    assert niveau_diplome("Maîtrise après baccalauréat") is NiveauDiplome.MAITRISE


def test_niveaux_de_langue():
    assert niveau_langue("Anglais courant") is NiveauLangue.C1
    assert niveau_langue("bilingue") is NiveauLangue.C2
    assert niveau_langue("Langue maternelle") is NiveauLangue.NATIF
    assert niveau_langue("B2") is NiveauLangue.B2


def test_codes_de_langue():
    assert code_langue("Anglais") == "en"
    assert code_langue("English") == "en"
    assert code_langue("Français") == "fr"
    assert code_langue("Klingon") == "klingon"


def test_normalisation_des_competences():
    assert normaliser_competence("Python 3") == "python"
    assert normaliser_competence("  PYTHON  ") == "python"
    assert normaliser_competence("NodeJS") == "node.js"
    assert normaliser_competence("Node.js") == "node.js"
    assert normaliser_competence("K8s") == "kubernetes"
    assert normaliser_competence("C#") == "c#"
    assert normaliser_competence(".NET Core") == ".net"
    assert normaliser_competence("Terraform,") == "terraform"
