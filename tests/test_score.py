from resume_ai import score


def poste(titre, organisation="", description=""):
    return {"titre": titre, "organisation": organisation, "description": description}


def test_le_parcours_reprend_ce_que_la_personne_a_fait():
    texte = score.parcours(
        [
            poste("Superviseure", "Assurances Boisvert", "Supervision de douze agents."),
            poste("Agente", "Télécom Rivard", "Réception des appels entrants."),
        ]
    )
    assert "Superviseure — Assurances Boisvert" in texte
    assert "Supervision de douze agents." in texte
    assert "Réception des appels entrants." in texte


def test_un_poste_sans_description_reste_identifiable():
    assert score.parcours([poste("Commis de bureau")]) == "Commis de bureau"


def test_les_postes_vides_sont_ecartes():
    assert score.parcours([poste(""), poste("  ")]) == ""


def test_scorer_ne_charge_rien_sans_matiere():
    """Ni parcours exploitable ni question : aucun appel au modèle."""
    sentinelle = object()
    assert score.scorer(sentinelle, {}, "Le parcours décrit-il ... ?") == {}
    assert score.scorer(sentinelle, {1: "   "}, "Le parcours décrit-il ... ?") == {}
    assert score.scorer(sentinelle, {1: "Agente"}, "  ") == {}
