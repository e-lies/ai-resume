import { useCallback, useEffect, useState } from 'react'
import Recherche from './Recherche'
import Televersement from './Televersement'
import { lireEtat, listerCv } from './api'

export default function App() {
  const [etat, setEtat] = useState(null)
  const [corpus, setCorpus] = useState([])
  const [injoignable, setInjoignable] = useState(false)

  const rafraichir = useCallback(() => {
    lireEtat()
      .then((valeur) => {
        setEtat(valeur)
        setInjoignable(false)
      })
      .catch(() => setInjoignable(true))
    listerCv()
      .then(setCorpus)
      .catch(() => setCorpus([]))
  }, [])

  useEffect(() => {
    rafraichir()
  }, [rafraichir])

  return (
    <div className="page">
      <header className="entete">
        <h1>resume-ai</h1>
        <p className="sous-titre">
          Recherche en langage naturel dans une base de CV.
        </p>
        {injoignable && (
          <p className="erreur">
            API injoignable — démarrez le serveur avec&nbsp;
            <code>uvicorn resume_ai.api:app --reload</code>
          </p>
        )}
        {etat && (
          <p className="etat">
            {etat.cv} CV en base · modèle {etat.modele}
            {!etat.cle_presente && (
              <span className="alerte"> · clé GEMINI_API_KEY absente</span>
            )}
            {etat.obsoletes > 0 && (
              <span className="alerte">
                {' '}
                · {etat.obsoletes} CV dans un format antérieur (
                <code>resume-ai reextraire</code>)
              </span>
            )}
          </p>
        )}
      </header>

      <main className="colonnes">
        <Televersement onIngestion={rafraichir} />
        <Recherche corpus={corpus} />
      </main>

      <footer className="pied">
        Un CV est un renseignement personnel. Ne téléversez ici que des fichiers
        dont le traitement est autorisé, et rappelez-vous qu'un fichier transmis
        ne peut plus être retiré du traitement déjà effectué.
      </footer>
    </div>
  )
}
