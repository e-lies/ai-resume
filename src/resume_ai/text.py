"""Conversion des fichiers CV en texte brut."""

from pathlib import Path

EXTENSIONS_SUPPORTEES = {".pdf", ".docx", ".txt"}


class LectureImpossible(RuntimeError):
    pass


def _lire_pdf(chemin: Path) -> str:
    import pdfplumber

    with pdfplumber.open(chemin) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _lire_docx(chemin: Path) -> str:
    import docx

    document = docx.Document(str(chemin))
    morceaux = [p.text for p in document.paragraphs]
    # Beaucoup de CV Word placent l'essentiel dans des tableaux, invisibles
    # pour `document.paragraphs`.
    for tableau in document.tables:
        for ligne in tableau.rows:
            morceaux.append(" | ".join(cellule.text.strip() for cellule in ligne.cells))
    return "\n".join(m for m in morceaux if m.strip())


def lire_texte(chemin: Path) -> str:
    extension = chemin.suffix.lower()
    if extension == ".pdf":
        texte = _lire_pdf(chemin)
    elif extension == ".docx":
        texte = _lire_docx(chemin)
    elif extension == ".txt":
        texte = chemin.read_text(encoding="utf-8")
    elif extension == ".doc":
        raise LectureImpossible("format .doc non pris en charge, convertir en .docx")
    else:
        raise LectureImpossible(f"extension non prise en charge : {extension}")

    if len(texte.strip()) < 50:
        raise LectureImpossible(
            "aucun texte exploitable (document numérisé ? une passe OCR est nécessaire)"
        )
    return texte
