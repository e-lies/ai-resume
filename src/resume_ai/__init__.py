"""resume-ai — recherche en langage naturel dans une base de CV."""

from dotenv import load_dotenv

# Chargé ici plutôt que dans les points d'entrée : l'import du paquet précède
# celui de tout module qui lit os.environ, dont `extraction` pour le modèle.
load_dotenv()
