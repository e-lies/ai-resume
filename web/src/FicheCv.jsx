import { useState } from 'react'
import { ajouterNote, supprimerNote } from './api'
import {
  formatDate,
  formatDuree,
  formatPeriode,
  nomDiplome,
  nomLangue,
} from './format'

const CLE_AUTEUR = 'resume-ai.auteur'

function lireAuteur() {
  try {
    return localStorage.getItem(CLE_AUTEUR) || ''
  } catch {
    return ''
  }
}

function retenirAuteur(valeur) {
  try {
    localStorage.setItem(CLE_AUTEUR, valeur)
  } catch {
    // Navigation privée ou stockage bloqué : sans importance.
  }
}

export default function FicheCv({ cv }) {
  const [notes, setNotes] = useState(cv.notes || [])
  const [parcoursOuvert, setParcoursOuvert] = useState(false)
  const [notesOuvertes, setNotesOuvertes] = useState(false)
  const [auteur, setAuteur] = useState(lireAuteur)
  const [contenu, setContenu] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(null)

  async function soumettre(evenement) {
    evenement.preventDefault()
    if (!auteur.trim() || !contenu.trim()) return
    setEnvoi(true)
    setErreur(null)
    try {
      setNotes(await ajouterNote(cv.id, auteur.trim(), contenu.trim()))
      retenirAuteur(auteur.trim())
      setContenu('')
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  async function retirer(noteId) {
    try {
      await supprimerNote(noteId)
      setNotes(notes.filter((note) => note.id !== noteId))
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <article className="fiche">
      <header className="fiche-entete">
        <h3>{cv.fichier}</h3>
        {typeof cv.score === 'number' && (
          <span
            className="etiquette etiquette-score"
            title="Probabilité que le parcours réponde oui à la question posée"
          >
            {Math.round(cv.score * 100)} %
          </span>
        )}
        {cv.diplome && (
          <span className="etiquette etiquette-diplome">
            {nomDiplome(cv.diplome.niveau)}
          </span>
        )}
      </header>

      {cv.diplome && (
        <p className="fiche-diplome">
          {cv.diplome.intitule}
          {cv.diplome.annee ? ` (${cv.diplome.annee})` : ''}
        </p>
      )}

      {cv.langues.length > 0 && (
        <p className="fiche-langues">
          {cv.langues.map((langue) => (
            <span key={langue.code} className="etiquette">
              {nomLangue(langue.code)} · {langue.niveau.toUpperCase()}
            </span>
          ))}
        </p>
      )}

      {cv.fonctions?.length > 0 && (
        <p className="fiche-fonctions">
          {cv.fonctions.map((fonction) => (
            <span key={fonction.nom} className="etiquette etiquette-fonction">
              {fonction.nom} · {formatDuree(fonction.mois)}
            </span>
          ))}
        </p>
      )}

      {cv.competences.length > 0 && (
        <ul className="fiche-competences">
          {cv.competences.map((competence) => (
            <li key={competence.nom}>
              <span className="competence-nom">{competence.nom}</span>
              <span
                className={
                  competence.source === 'poste' ? 'duree' : 'duree duree-declaree'
                }
                title={
                  competence.source === 'poste'
                    ? 'Calculée à partir des dates de postes'
                    : 'Listée dans le CV, sans poste daté'
                }
              >
                {formatDuree(competence.mois)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="fiche-sections">
        {cv.postes?.length > 0 && (
          <button
            type="button"
            className="lien"
            onClick={() => setParcoursOuvert(!parcoursOuvert)}
          >
            {parcoursOuvert ? 'Masquer le parcours' : `Parcours (${cv.postes.length})`}
          </button>
        )}
        <button
          type="button"
          className="lien"
          onClick={() => setNotesOuvertes(!notesOuvertes)}
        >
          {notesOuvertes ? 'Masquer les notes' : `Notes (${notes.length})`}
        </button>
      </div>

      {parcoursOuvert && (
        <ol className="parcours">
          {cv.postes.map((poste, index) => (
            <li key={`${poste.debut}-${index}`}>
              <p className="parcours-titre">
                {poste.titre}
                {poste.organisation ? ` — ${poste.organisation}` : ''}
              </p>
              <p className="parcours-periode">
                {formatPeriode(poste.debut, poste.fin)}
              </p>
              {poste.description && (
                <p className="parcours-description">{poste.description}</p>
              )}
            </li>
          ))}
        </ol>
      )}

      {notesOuvertes && (
        <div className="notes">
          {notes.length === 0 && <p className="note">Aucune note.</p>}
          {notes.map((note) => (
            <div key={note.id} className="note-entree">
              <p className="note-meta">
                {note.auteur} · {formatDate(note.cree_le)}
                <button
                  type="button"
                  className="lien note-retirer"
                  onClick={() => retirer(note.id)}
                >
                  supprimer
                </button>
              </p>
              <p className="note-contenu">{note.contenu}</p>
            </div>
          ))}

          <form onSubmit={soumettre} className="note-formulaire">
            <input
              value={auteur}
              onChange={(e) => setAuteur(e.target.value)}
              placeholder="Vos initiales"
              aria-label="Auteur de la note"
            />
            <textarea
              value={contenu}
              onChange={(e) => setContenu(e.target.value)}
              placeholder="Entrevue du 12 mars : à l'aise sur la gestion d'équipe, veut du télétravail."
              rows={2}
            />
            <button type="submit" disabled={envoi || !auteur.trim() || !contenu.trim()}>
              {envoi ? 'Ajout…' : 'Ajouter la note'}
            </button>
          </form>

          {erreur && <p className="erreur">{erreur}</p>}
        </div>
      )}
    </article>
  )
}
