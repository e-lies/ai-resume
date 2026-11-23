import { useState } from 'react'
import FicheCv from './FicheCv'
import { rechercher } from './api'

const EXEMPLE =
  "profils avec au moins une maîtrise, parlant anglais, et 4 ans ou plus d'expérience en Python"

const pluriel = (nombre, mot) => `${nombre} ${mot}${nombre > 1 ? 's' : ''}`

export default function Recherche({ corpus }) {
  const [question, setQuestion] = useState('')
  const [reponse, setReponse] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [montrerSql, setMontrerSql] = useState(false)
  const [classer, setClasser] = useState(false)

  async function soumettre(evenement) {
    evenement.preventDefault()
    if (!question.trim()) return
    setChargement(true)
    setErreur(null)
    try {
      setReponse(await rechercher(question, classer))
    } catch (e) {
      setErreur(e.message)
      setReponse(null)
    } finally {
      setChargement(false)
    }
  }

  function reinitialiser() {
    setReponse(null)
    setErreur(null)
    setQuestion('')
  }

  const profils = reponse ? reponse.resultats : corpus

  return (
    <section className="panneau">
      <h2>Rechercher</h2>

      <form onSubmit={soumettre} className="formulaire">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={EXEMPLE}
          rows={3}
        />
        <div className="barre-actions">
          <button
            type="button"
            className="lien"
            onClick={() => setQuestion(EXEMPLE)}
          >
            Utiliser l'exemple
          </button>
          <label className="option-classer">
            <input
              type="checkbox"
              checked={classer}
              onChange={(e) => setClasser(e.target.checked)}
            />
            Classer par pertinence
          </label>
          <button type="submit" disabled={chargement || !question.trim()}>
            {chargement ? 'Recherche…' : 'Rechercher'}
          </button>
        </div>
      </form>

      {erreur && <p className="erreur">{erreur}</p>}

      {reponse && (
        <div className="criteres">
          <h3>Critères interprétés</h3>
          {reponse.criteres.length ? (
            <ul>
              {reponse.criteres.map((critere) => (
                <li key={critere}>{critere}</li>
              ))}
            </ul>
          ) : (
            <p className="note">Aucun critère retenu — la requête a tout gardé.</p>
          )}
          {classer && reponse.question_verification && (
            <p className="question-verification">
              Question posée à chaque parcours : « {reponse.question_verification} »
            </p>
          )}
          <button
            type="button"
            className="lien"
            onClick={() => setMontrerSql(!montrerSql)}
          >
            {montrerSql ? 'Masquer le SQL' : 'Voir le SQL'}
          </button>
          {montrerSql && <pre className="sql">{reponse.sql}</pre>}
        </div>
      )}

      <div className="barre-resultats">
        <p className="compte">
          {reponse
            ? pluriel(profils.length, 'profil')
            : `${pluriel(profils.length, 'profil')} en base`}
        </p>
        {reponse && (
          <button type="button" className="lien" onClick={reinitialiser}>
            Voir tout le corpus
          </button>
        )}
      </div>

      {profils.length === 0 ? (
        <p className="note">
          {reponse
            ? 'Aucun profil ne satisfait ces critères.'
            : 'La base est vide — téléversez des CV pour commencer.'}
        </p>
      ) : (
        <div className="resultats">
          {profils.map((cv) => (
            <FicheCv key={cv.id} cv={cv} />
          ))}
        </div>
      )}
    </section>
  )
}
