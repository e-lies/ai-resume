"""API HTTP au-dessus du pipeline d'extraction, consommée par l'interface React."""

import os
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import score, store
from .extraction import MODELE_DEFAUT, creer_client, extraire_profil
from .query import VOCABULAIRE_MAX, compiler, criteres_lisibles, traduire
from .text import EXTENSIONS_SUPPORTEES, lire_texte

BASE = Path(os.environ.get("RESUME_AI_BASE", "resume-ai.db"))
CORPUS = Path(os.environ.get("RESUME_AI_CORPUS", "corpus"))

app = FastAPI(title="resume-ai")


class DemandeRecherche(BaseModel):
    question: str
    classer: bool = False


class DemandeNote(BaseModel):
    auteur: str
    contenu: str


def _client():
    try:
        return creer_client()
    except RuntimeError as erreur:
        raise HTTPException(503, str(erreur))


def _resumer(connexion, lignes) -> list[dict]:
    identifiants = [l["id"] for l in lignes]
    details = store.detailler(connexion, identifiants)
    notes = store.notes(connexion, identifiants)
    resumes = []
    for ligne in lignes:
        detail = details[ligne["id"]]
        diplomes = detail["diplomes"]
        resumes.append(
            {
                "id": ligne["id"],
                "fichier": Path(ligne["source"]).name,
                "diplome": diplomes[0] if diplomes else None,
                "langues": detail["langues"],
                "fonctions": detail["fonctions"][:8],
                "competences": detail["competences"][:12],
                "postes": detail["postes"],
                "notes": notes[ligne["id"]],
            }
        )
    return resumes


def _classer(resultats: list[dict], question: str) -> list[dict]:
    """Ordonne par probabilité décroissante, en ne scorant que le haut de la liste.

    Environ 100 ms par profil sur processeur : au-delà du plafond, la recherche
    cesserait d'être interactive. Les profils non scorés restent à la fin, dans
    l'ordre du filtre SQL.
    """
    try:
        agent = score.charger()
    except score.ScoreIndisponible as erreur:
        raise HTTPException(503, str(erreur))

    a_scorer = resultats[: score.PLAFOND_DEFAUT]
    scores = score.scorer(
        agent,
        {resultat["id"]: score.parcours(resultat["postes"]) for resultat in a_scorer},
        question,
    )
    for resultat in resultats:
        resultat["score"] = scores.get(resultat["id"])
    return sorted(
        resultats, key=lambda r: (r["score"] is None, -(r["score"] or 0.0))
    )


def _verifier_cv(connexion, cv_id: int) -> None:
    if connexion.execute("select 1 from cv where id = ?", (cv_id,)).fetchone() is None:
        raise HTTPException(404, f"CV {cv_id} introuvable")


@app.get("/api/etat")
def etat():
    connexion = store.ouvrir(BASE)
    try:
        total = connexion.execute("select count(*) as n from cv").fetchone()["n"]
        obsoletes = len(store.obsoletes(connexion))
    finally:
        connexion.close()
    cle_presente = bool(
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    return {
        "cv": total,
        "obsoletes": obsoletes,
        "modele": MODELE_DEFAUT,
        "cle_presente": cle_presente,
    }


@app.get("/api/cv")
def lister():
    connexion = store.ouvrir(BASE)
    try:
        lignes = list(
            connexion.execute("select id, source from cv order by extrait_le desc, id desc")
        )
        return _resumer(connexion, lignes)
    finally:
        connexion.close()


@app.post("/api/cv")
def televerser(fichier: UploadFile = File(...)):
    # `Path(...).name` neutralise toute tentative de traversée de répertoire.
    nom = Path(fichier.filename or "").name
    extension = Path(nom).suffix.lower()
    if not nom or extension not in EXTENSIONS_SUPPORTEES:
        raise HTTPException(
            415, f"extension non prise en charge : {extension or 'aucune'}"
        )

    CORPUS.mkdir(parents=True, exist_ok=True)
    destination = CORPUS / nom
    with destination.open("wb") as sortie:
        shutil.copyfileobj(fichier.file, sortie)

    client = _client()
    try:
        texte = lire_texte(destination)
        profil = extraire_profil(client, texte)
    except Exception as erreur:
        raise HTTPException(422, f"{nom} : {erreur}")

    connexion = store.ouvrir(BASE)
    try:
        cv_id = store.enregistrer(connexion, str(destination), texte, profil)
        ligne = connexion.execute(
            "select id, source from cv where id = ?", (cv_id,)
        ).fetchone()
        return _resumer(connexion, [ligne])[0]
    finally:
        connexion.close()


@app.post("/api/cv/{cv_id}/notes")
def ajouter_note(cv_id: int, demande: DemandeNote):
    if not demande.contenu.strip() or not demande.auteur.strip():
        raise HTTPException(400, "auteur et contenu sont obligatoires")
    connexion = store.ouvrir(BASE)
    try:
        _verifier_cv(connexion, cv_id)
        store.ajouter_note(
            connexion, cv_id, demande.auteur.strip(), demande.contenu.strip()
        )
        return store.notes(connexion, [cv_id])[cv_id]
    finally:
        connexion.close()


@app.delete("/api/notes/{note_id}")
def supprimer_note(note_id: int):
    connexion = store.ouvrir(BASE)
    try:
        if not store.supprimer_note(connexion, note_id):
            raise HTTPException(404, f"note {note_id} introuvable")
        return {"supprimee": note_id}
    finally:
        connexion.close()


@app.post("/api/recherche")
def rechercher(demande: DemandeRecherche):
    if not demande.question.strip():
        raise HTTPException(400, "question vide")

    connexion = store.ouvrir(BASE)
    try:
        requete = traduire(
            _client(),
            demande.question,
            [l["nom"] for l in store.vocabulaire(connexion, VOCABULAIRE_MAX, "competence")],
            [l["nom"] for l in store.vocabulaire(connexion, VOCABULAIRE_MAX, "fonction")],
        )
        sql, parametres = compiler(requete)
        lignes = list(connexion.execute(sql, parametres))
        resultats = _resumer(connexion, lignes)
        if demande.classer:
            resultats = _classer(resultats, requete.question_verification)
        return {
            "criteres": criteres_lisibles(requete),
            "question_verification": requete.question_verification,
            "sql": sql,
            "resultats": resultats,
        }
    finally:
        connexion.close()


@app.get("/api/vocabulaire")
def vocabulaire(limite: int = 60, dimension: str = "competence"):
    if dimension not in store.DIMENSIONS:
        raise HTTPException(400, f"dimension inconnue : {dimension}")
    connexion = store.ouvrir(BASE)
    try:
        return [
            dict(ligne) for ligne in store.vocabulaire(connexion, limite, dimension)
        ]
    finally:
        connexion.close()
