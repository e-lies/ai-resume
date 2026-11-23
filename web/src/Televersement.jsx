import { useRef, useState } from 'react'
import { televerser } from './api'

// L'extraction est un appel au modèle par fichier : on en mène quelques-uns de
// front sans saturer l'API ni la base.
const CONCURRENCE = 3

const LIBELLES = {
  attente: 'en attente',
  encours: 'extraction…',
  ok: 'extrait',
  erreur: 'échec',
}

export default function Televersement({ onIngestion }) {
  const [entrees, setEntrees] = useState([])
  const [survol, setSurvol] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const champ = useRef(null)

  const majEntree = (id, modif) =>
    setEntrees((precedentes) =>
      precedentes.map((entree) =>
        entree.id === id ? { ...entree, ...modif } : entree,
      ),
    )

  async function traiter(listeFichiers) {
    const fichiers = Array.from(listeFichiers || [])
    if (!fichiers.length) return

    const horodatage = Date.now()
    const nouvelles = fichiers.map((fichier, index) => ({
      id: `${horodatage}-${index}`,
      nom: fichier.name,
      fichier,
      etat: 'attente',
    }))
    setEntrees((precedentes) => [...nouvelles, ...precedentes])
    setEnCours(true)

    const file = [...nouvelles]
    await Promise.all(
      Array.from({ length: CONCURRENCE }, async () => {
        while (file.length) {
          const entree = file.shift()
          majEntree(entree.id, { etat: 'encours' })
          try {
            const resultat = await televerser(entree.fichier)
            majEntree(entree.id, { etat: 'ok', resultat })
          } catch (erreur) {
            majEntree(entree.id, { etat: 'erreur', message: erreur.message })
          }
        }
      }),
    )

    setEnCours(false)
    onIngestion()
  }

  function deposer(evenement) {
    evenement.preventDefault()
    setSurvol(false)
    traiter(evenement.dataTransfer.files)
  }

  return (
    <section className="panneau">
      <h2>Téléverser des CV</h2>

      <div
        className={survol ? 'depot depot-survol' : 'depot'}
        onDragOver={(e) => {
          e.preventDefault()
          setSurvol(true)
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={deposer}
        onClick={() => champ.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && champ.current?.click()}
      >
        <p className="depot-titre">Glissez des fichiers ici</p>
        <p className="depot-detail">ou cliquez pour les choisir · PDF, DOCX, TXT</p>
        <input
          ref={champ}
          type="file"
          multiple
          accept=".pdf,.docx,.txt"
          hidden
          onChange={(e) => {
            traiter(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {enCours && <p className="note">Extraction en cours…</p>}

      {entrees.length > 0 && (
        <ul className="liste-fichiers">
          {entrees.map((entree) => (
            <li key={entree.id} className={`ligne-fichier etat-${entree.etat}`}>
              <span className="nom-fichier">{entree.nom}</span>
              <span className="etat-fichier">
                {entree.etat === 'erreur'
                  ? entree.message
                  : LIBELLES[entree.etat]}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
