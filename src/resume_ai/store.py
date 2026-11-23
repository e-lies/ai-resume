"""Persistance SQLite.

Le texte brut et le JSON d'extraction sont conservés : quand le schéma évolue,
on réextrait depuis la base sans relire ni repayer le parsing des fichiers.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .experience import experience_par_terme
from .models import VERSION_SCHEMA, ProfilCV
from .taxonomy import RANG_DIPLOME, RANG_LANGUE, code_langue, normaliser_competence

DIMENSIONS = ("competence", "fonction")

SCHEMA = """
create table if not exists cv (
    id integer primary key autoincrement,
    source text not null unique,
    extrait_le text not null,
    texte text not null,
    profil_json text not null,
    niveau_diplome_max integer not null,
    version_schema integer not null default 0
);

create table if not exists diplome (
    cv_id integer not null references cv(id) on delete cascade,
    intitule text not null,
    niveau text not null,
    rang integer not null,
    domaine text not null,
    etablissement text not null,
    annee integer
);

create table if not exists langue (
    cv_id integer not null references cv(id) on delete cascade,
    code text not null,
    niveau text not null,
    rang integer not null
);

create table if not exists poste (
    cv_id integer not null references cv(id) on delete cascade,
    titre text not null,
    organisation text not null,
    debut text not null,
    fin text,
    description text not null default ''
);

-- Supprimer un CV supprime ses notes, ce qui est voulu. Une réextraction, elle,
-- n'en est pas une suppression : `enregistrer` met la ligne `cv` à jour sans
-- changer son identifiant, précisément pour que les notes y survivent.
create table if not exists note (
    id integer primary key autoincrement,
    cv_id integer not null references cv(id) on delete cascade,
    cree_le text not null,
    auteur text not null,
    contenu text not null
);

create table if not exists competence (
    cv_id integer not null references cv(id) on delete cascade,
    nom text not null,
    nom_brut text not null,
    mois integer not null,
    source text not null
);

create table if not exists fonction (
    cv_id integer not null references cv(id) on delete cascade,
    nom text not null,
    nom_brut text not null,
    mois integer not null
);

-- Index composites calqués sur la forme des sous-requêtes EXISTS produites par
-- `query.compiler` : un index sur `nom` seul oblige à vérifier `cv_id` ligne à
-- ligne, ce qui coûte plus d'une seconde sur un corpus de quelques milliers de CV.
drop index if exists idx_competence_nom;
drop index if exists idx_fonction_nom;
drop index if exists idx_langue_code;

create index if not exists idx_competence_recherche on competence(nom, cv_id, mois, source);
create index if not exists idx_fonction_recherche on fonction(nom, cv_id, mois);
create index if not exists idx_langue_recherche on langue(code, cv_id, rang);
create index if not exists idx_cv_diplome on cv(niveau_diplome_max);
create index if not exists idx_diplome_cv on diplome(cv_id);
create index if not exists idx_poste_cv on poste(cv_id);
create index if not exists idx_note_cv on note(cv_id);
"""

# Tables entièrement recalculées à chaque extraction, contrairement à `note`.
TABLES_DERIVEES = ("diplome", "langue", "poste", "competence", "fonction")

# Ces colonnes figurent aussi dans SCHEMA, pour qu'une base neuve les ait d'emblée.
# Elles restent listées ici pour les bases créées avant leur introduction.
_COLONNES_AJOUTEES = [
    ("cv", "version_schema", "integer not null default 0"),
    ("poste", "description", "text not null default ''"),
]


def _migrer(connexion: sqlite3.Connection) -> None:
    """`create table if not exists` n'ajoute pas les colonnes d'une base existante."""
    for table, colonne, definition in _COLONNES_AJOUTEES:
        existantes = {
            ligne["name"] for ligne in connexion.execute(f"pragma table_info({table})")
        }
        if colonne not in existantes:
            connexion.execute(f"alter table {table} add column {colonne} {definition}")


def _migrer_note(connexion: sqlite3.Connection) -> None:
    """La table `note` a d'abord porté le chemin du fichier au lieu de `cv.id`.

    Doit tourner AVANT `SCHEMA` : `create table if not exists` ne répare pas une
    table existante, et l'index sur `note(cv_id)` échoue sur l'ancienne forme.
    Les notes étant irremplaçables, on les reporte par jointure sur `cv.source`
    plutôt que de repartir de zéro.
    """
    colonnes = {ligne["name"] for ligne in connexion.execute("pragma table_info(note)")}
    if not colonnes or "cv_id" in colonnes:
        return
    connexion.executescript(
        """
        alter table note rename to note_obsolete;

        create table note (
            id integer primary key autoincrement,
            cv_id integer not null references cv(id) on delete cascade,
            cree_le text not null,
            auteur text not null,
            contenu text not null
        );

        insert into note (cv_id, cree_le, auteur, contenu)
        select cv.id, note_obsolete.cree_le, note_obsolete.auteur, note_obsolete.contenu
        from note_obsolete join cv on cv.source = note_obsolete.source;

        drop table note_obsolete;
        """
    )


def ouvrir(chemin: Path | str) -> sqlite3.Connection:
    connexion = sqlite3.connect(chemin)
    connexion.row_factory = sqlite3.Row
    connexion.execute("pragma foreign_keys = on")
    _migrer_note(connexion)
    connexion.executescript(SCHEMA)
    _migrer(connexion)
    return connexion


def enregistrer(connexion: sqlite3.Connection, source: str, texte: str, profil: ProfilCV) -> int:
    niveau_max = max((RANG_DIPLOME[d.niveau] for d in profil.diplomes), default=0)

    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    valeurs = (horodatage, texte, profil.model_dump_json(), niveau_max, VERSION_SCHEMA)

    with connexion:
        existant = connexion.execute(
            "select id from cv where source = ?", (source,)
        ).fetchone()
        if existant:
            # Mise à jour et non suppression : la ligne garde son identifiant, donc
            # les notes qui s'y rattachent survivent à une réextraction. Seules les
            # tables dérivées sont reconstruites.
            cv_id = existant["id"]
            connexion.execute(
                "update cv set extrait_le = ?, texte = ?, profil_json = ?,"
                " niveau_diplome_max = ?, version_schema = ? where id = ?",
                valeurs + (cv_id,),
            )
            for table in TABLES_DERIVEES:
                connexion.execute(f"delete from {table} where cv_id = ?", (cv_id,))
        else:
            curseur = connexion.execute(
                "insert into cv (source, extrait_le, texte, profil_json,"
                " niveau_diplome_max, version_schema) values (?, ?, ?, ?, ?, ?)",
                (source,) + valeurs,
            )
            cv_id = curseur.lastrowid

        connexion.executemany(
            "insert into diplome (cv_id, intitule, niveau, rang, domaine, etablissement, annee)"
            " values (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cv_id,
                    d.intitule,
                    d.niveau.value,
                    RANG_DIPLOME[d.niveau],
                    d.domaine,
                    d.etablissement,
                    d.annee_obtention,
                )
                for d in profil.diplomes
            ],
        )

        connexion.executemany(
            "insert into langue (cv_id, code, niveau, rang) values (?, ?, ?, ?)",
            [
                (cv_id, code_langue(l.langue), l.niveau.value, RANG_LANGUE[l.niveau])
                for l in profil.langues
            ],
        )

        connexion.executemany(
            "insert into poste (cv_id, titre, organisation, debut, fin, description)"
            " values (?, ?, ?, ?, ?, ?)",
            [
                (cv_id, p.titre, p.organisation, p.debut, p.fin, p.description)
                for p in profil.postes
            ],
        )

        experiences = experience_par_terme(profil.postes)
        lignes = [
            (cv_id, nom, exp.nom_brut, exp.mois, "poste")
            for nom, exp in experiences.items()
        ]
        deja_vues = set(experiences)
        for brut in profil.competences_declarees:
            nom = normaliser_competence(brut)
            if not nom or nom in deja_vues:
                continue
            deja_vues.add(nom)
            lignes.append((cv_id, nom, brut, 0, "declaree"))

        connexion.executemany(
            "insert into competence (cv_id, nom, nom_brut, mois, source) values (?, ?, ?, ?, ?)",
            lignes,
        )

        connexion.executemany(
            "insert into fonction (cv_id, nom, nom_brut, mois) values (?, ?, ?, ?)",
            [
                (cv_id, nom, exp.nom_brut, exp.mois)
                for nom, exp in experience_par_terme(
                    profil.postes, lambda poste: poste.fonctions
                ).items()
            ],
        )

    return cv_id


def sources_connues(connexion: sqlite3.Connection) -> set[str]:
    return {ligne["source"] for ligne in connexion.execute("select source from cv")}


def obsoletes(connexion: sqlite3.Connection) -> list[sqlite3.Row]:
    """CV enregistrés sous une version antérieure du schéma d'extraction."""
    return list(
        connexion.execute(
            "select id, source, texte, version_schema from cv"
            " where version_schema < ? order by id",
            (VERSION_SCHEMA,),
        )
    )


def supprimer(connexion: sqlite3.Connection, cv_ids: list[int]) -> int:
    if not cv_ids:
        return 0
    trous = ",".join("?" * len(cv_ids))
    with connexion:
        curseur = connexion.execute(f"delete from cv where id in ({trous})", cv_ids)
    return curseur.rowcount


def detailler(connexion: sqlite3.Connection, cv_ids: list[int]) -> dict[int, dict]:
    """Contenu affichable de chaque CV : diplômes, langues, compétences, fonctions."""
    if not cv_ids:
        return {}
    trous = ",".join("?" * len(cv_ids))
    details: dict[int, dict] = {
        cv_id: {
            "diplomes": [],
            "langues": [],
            "competences": [],
            "fonctions": [],
            "postes": [],
        }
        for cv_id in cv_ids
    }
    requetes = {
        "diplomes": "select cv_id, intitule, niveau, domaine, annee from diplome"
        f" where cv_id in ({trous}) order by rang desc",
        "postes": "select cv_id, titre, organisation, debut, fin, description from poste"
        f" where cv_id in ({trous}) order by debut desc",
        "langues": "select cv_id, code, niveau from langue"
        f" where cv_id in ({trous}) order by rang desc",
        "competences": "select cv_id, nom, mois, source from competence"
        f" where cv_id in ({trous}) order by mois desc, nom",
        "fonctions": "select cv_id, nom, mois from fonction"
        f" where cv_id in ({trous}) order by mois desc, nom",
    }
    for cle, sql in requetes.items():
        for ligne in connexion.execute(sql, cv_ids):
            details[ligne["cv_id"]][cle].append(
                {k: ligne[k] for k in ligne.keys() if k != "cv_id"}
            )
    return details


def ajouter_note(
    connexion: sqlite3.Connection, cv_id: int, auteur: str, contenu: str
) -> int:
    """L'auteur et la date sont obligatoires : une note est un renseignement
    personnel sur un candidat, qui peut en demander l'accès ou la rectification."""
    with connexion:
        curseur = connexion.execute(
            "insert into note (cv_id, cree_le, auteur, contenu) values (?, ?, ?, ?)",
            (
                cv_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                auteur,
                contenu,
            ),
        )
    return curseur.lastrowid


def supprimer_note(connexion: sqlite3.Connection, note_id: int) -> int:
    with connexion:
        curseur = connexion.execute("delete from note where id = ?", (note_id,))
    return curseur.rowcount


def notes(connexion: sqlite3.Connection, cv_ids: list[int]) -> dict[int, list[dict]]:
    if not cv_ids:
        return {}
    trous = ",".join("?" * len(cv_ids))
    groupes: dict[int, list[dict]] = {cv_id: [] for cv_id in cv_ids}
    for ligne in connexion.execute(
        "select id, cv_id, cree_le, auteur, contenu from note"
        f" where cv_id in ({trous}) order by cree_le desc, id desc",
        cv_ids,
    ):
        groupes[ligne["cv_id"]].append(
            {k: ligne[k] for k in ligne.keys() if k != "cv_id"}
        )
    return groupes


def vocabulaire(
    connexion: sqlite3.Connection, limite: int = 100, dimension: str = "competence"
) -> list[sqlite3.Row]:
    """Termes normalisés d'une dimension, par fréquence.

    Sert à repérer les alias manquants, et alimente la traduction des questions :
    le modèle voit le vocabulaire réel du corpus et peut y rattacher la demande.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension inconnue : {dimension}")
    return list(
        connexion.execute(
            "select nom, count(*) as cvs, min(nom_brut) as exemple"
            f" from {dimension} group by nom order by cvs desc, nom limit ?",
            (limite,),
        )
    )
