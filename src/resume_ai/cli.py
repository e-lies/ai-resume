"""Interface en ligne de commande."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import store
from .extraction import MODELE_DEFAUT, creer_client, extraire_profil
from .query import VOCABULAIRE_MAX, compiler, resumer, traduire
from .text import EXTENSIONS_SUPPORTEES, lire_texte


def _traiter_lot(elements, travail, paralleles):
    """Exécute `travail` sur chaque élément, rend (element, resultat, erreur)."""
    with ThreadPoolExecutor(max_workers=paralleles) as pool:
        futurs = {pool.submit(travail, element): element for element in elements}
        for futur in as_completed(futurs):
            element = futurs[futur]
            try:
                yield element, futur.result(), None
            except Exception as erreur:
                yield element, None, erreur


def _ingerer(args, connexion) -> int:
    fichiers = [
        f
        for f in sorted(args.dossier.rglob("*"))
        if f.is_file() and f.suffix.lower() in EXTENSIONS_SUPPORTEES
    ]
    if not args.tout:
        connues = store.sources_connues(connexion)
        fichiers = [f for f in fichiers if str(f) not in connues]

    if not fichiers:
        print("Rien à traiter.")
        return 0

    print(f"{len(fichiers)} fichier(s) à extraire avec {args.modele}.")
    client = creer_client()

    def travail(fichier):
        texte = lire_texte(fichier)
        return texte, extraire_profil(client, texte, args.modele)

    echecs = 0
    for fichier, resultat, erreur in _traiter_lot(fichiers, travail, args.paralleles):
        if erreur:
            echecs += 1
            print(f"  échec  {fichier.name} : {erreur}")
            continue
        texte, profil = resultat
        store.enregistrer(connexion, str(fichier), texte, profil)
        print(f"  ok     {fichier.name}")

    print(f"Terminé : {len(fichiers) - echecs} extraits, {echecs} en échec.")
    return 1 if echecs else 0


def _reextraire(args, connexion) -> int:
    lignes = store.obsoletes(connexion)
    if not lignes:
        print("Aucun CV dans un format antérieur.")
        return 0

    print(f"{len(lignes)} CV dans un format antérieur.")
    if args.supprimer:
        nombre = store.supprimer(connexion, [ligne["id"] for ligne in lignes])
        print(f"{nombre} entrée(s) supprimée(s).")
        return 0

    client = creer_client()
    echecs = 0
    # Le texte est déjà en base : on ne relit aucun fichier et on ne repaie
    # ni la lecture des PDF ni celle des documents Word.
    for ligne, profil, erreur in _traiter_lot(
        lignes,
        lambda ligne: extraire_profil(client, ligne["texte"], args.modele),
        args.paralleles,
    ):
        if erreur:
            echecs += 1
            print(f"  échec  {ligne['source']} : {erreur}")
            continue
        store.enregistrer(connexion, ligne["source"], ligne["texte"], profil)
        print(f"  ok     {ligne['source']}")

    print(f"Terminé : {len(lignes) - echecs} réextraits, {echecs} en échec.")
    return 1 if echecs else 0


def _chercher(args, connexion) -> int:
    requete = traduire(
        creer_client(),
        args.question,
        [l["nom"] for l in store.vocabulaire(connexion, VOCABULAIRE_MAX, "competence")],
        [l["nom"] for l in store.vocabulaire(connexion, VOCABULAIRE_MAX, "fonction")],
        args.modele,
    )

    print("Critères interprétés :")
    print(resumer(requete))

    sql, parametres = compiler(requete)
    if args.sql:
        print(f"\nSQL : {sql}\nParamètres : {parametres}")

    resultats = list(connexion.execute(sql, parametres))
    print(f"\n{len(resultats)} profil(s) :")
    for ligne in resultats:
        print(f"  {ligne['source']}")
    return 0


def _vocabulaire(args, connexion) -> int:
    for ligne in store.vocabulaire(connexion, args.limite, args.dimension):
        print(f"{ligne['cvs']:5d}  {ligne['nom']:<28} (ex. « {ligne['exemple']} »)")
    return 0


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(prog="resume-ai")
    parseur.add_argument("--base", default="resume-ai.db", help="fichier SQLite")
    sous = parseur.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("ingerer", help="extrait les CV d'un dossier")
    p.add_argument("dossier", type=Path)
    p.add_argument("--modele", default=MODELE_DEFAUT)
    p.add_argument("--paralleles", type=int, default=4)
    p.add_argument("--tout", action="store_true", help="réextraire les CV déjà en base")
    p.set_defaults(fonction=_ingerer)

    p = sous.add_parser(
        "reextraire", help="met à jour les CV enregistrés sous un format antérieur"
    )
    p.add_argument("--modele", default=MODELE_DEFAUT)
    p.add_argument("--paralleles", type=int, default=4)
    p.add_argument(
        "--supprimer",
        action="store_true",
        help="supprimer ces entrées au lieu de les réextraire",
    )
    p.set_defaults(fonction=_reextraire)

    p = sous.add_parser("chercher", help="interroge la base en langage naturel")
    p.add_argument("question")
    p.add_argument("--modele", default=MODELE_DEFAUT)
    p.add_argument("--sql", action="store_true", help="affiche la requête compilée")
    p.set_defaults(fonction=_chercher)

    p = sous.add_parser("vocabulaire", help="termes extraits, par fréquence")
    p.add_argument("--limite", type=int, default=50)
    p.add_argument("--dimension", choices=store.DIMENSIONS, default="competence")
    p.set_defaults(fonction=_vocabulaire)

    args = parseur.parse_args(argv)
    connexion = store.ouvrir(args.base)
    try:
        return args.fonction(args, connexion)
    except RuntimeError as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 2
    finally:
        connexion.close()


if __name__ == "__main__":
    sys.exit(main())
