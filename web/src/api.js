async function appeler(url, options) {
  const reponse = await fetch(url, options)
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => ({}))
    throw new Error(corps.detail || `Erreur ${reponse.status}`)
  }
  return reponse.json()
}

export function lireEtat() {
  return appeler('/api/etat')
}

export function listerCv() {
  return appeler('/api/cv')
}

export function televerser(fichier) {
  const corps = new FormData()
  corps.append('fichier', fichier)
  return appeler('/api/cv', { method: 'POST', body: corps })
}

export function ajouterNote(cvId, auteur, contenu) {
  return appeler(`/api/cv/${cvId}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auteur, contenu }),
  })
}

export function supprimerNote(noteId) {
  return appeler(`/api/notes/${noteId}`, { method: 'DELETE' })
}

export function rechercher(question, classer = false) {
  return appeler('/api/recherche', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, classer }),
  })
}
