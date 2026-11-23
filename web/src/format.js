const LANGUES = {
  fr: 'Français',
  en: 'Anglais',
  es: 'Espagnol',
  de: 'Allemand',
  it: 'Italien',
  pt: 'Portugais',
  ar: 'Arabe',
  zh: 'Mandarin',
}

const DIPLOMES = {
  secondaire: 'Secondaire',
  collegial: 'Collégial',
  certificat: 'Certificat',
  baccalaureat: 'Baccalauréat',
  dess: 'DESS',
  maitrise: 'Maîtrise',
  doctorat: 'Doctorat',
}

export const nomLangue = (code) => LANGUES[code] || code
export const nomDiplome = (niveau) => DIPLOMES[niveau] || niveau

const MOIS = [
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
  'juill.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
]

function moisAnnee(valeur) {
  if (!valeur) return ''
  const [annee, mois] = valeur.split('-')
  return `${MOIS[Number(mois) - 1] || ''} ${annee}`.trim()
}

export function formatPeriode(debut, fin) {
  return fin ? `${moisAnnee(debut)} – ${moisAnnee(fin)}` : `depuis ${moisAnnee(debut)}`
}

export function formatDate(iso) {
  return iso ? iso.slice(0, 10) : ''
}

export function formatDuree(mois) {
  if (!mois) return 'déclarée'
  const annees = Math.floor(mois / 12)
  const reste = mois % 12
  const partAnnees = annees ? `${annees} an${annees > 1 ? 's' : ''}` : ''
  const partMois = reste ? `${reste} mois` : ''
  return [partAnnees, partMois].filter(Boolean).join(' ')
}
