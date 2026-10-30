#!/usr/bin/env python3
"""
Parse le DOCX (texte natif, sans OCR) du Code pénal camerounais (Loi 2016/007)
en JSON hiérarchique : Code > Livre > Titre > Chapitre > Section > Article > Alinéa.

Usage : python parse_docx.py code.docx sortie.json
(nécessite pandoc)
"""
import json
import re
import subprocess
import sys

RE_LIVRE = re.compile(r"^LIVRE\s+([IVX]+)\s*$")
RE_TITRE = re.compile(r"^TITRE\s+([IVX]+)\s*$")
RE_CHAPITRE = re.compile(r"^CHAPITRE\s+([IVX]+)\s*$")
RE_SECTION = re.compile(r"^SECTION\s+([IVX]+)\s*:?\s*$")
RE_ARTICLE = re.compile(r"^ARTICLE\s+(\d+(?:-\d+)?)\s*\.?\s*-?\s*(.*)$")
RE_ARTICLES_RANGE = re.compile(r"^ARTICLES\s+(\d+)\s+à\s+(\d+)\s*\.?\s*-?\s*(.*)$")
RE_ALINEA = re.compile(r"^\((\d+)\)\s*(.*)$")
RE_PAGE = re.compile(r"^\d{1,3}$")
RE_CAPS = re.compile(r"^[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ0-9][A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ0-9\s'’,\-–()/.]*$")


def read_paragraphs(docx_path):
    txt = subprocess.run(
        ["pandoc", "-t", "plain", "--wrap=none", docx_path],
        capture_output=True, text=True, check=True,
    ).stdout
    paras = []
    for l in txt.split("\n"):
        l = l.strip()
        if not l or RE_PAGE.match(l) or set(l) <= set("- "):
            continue
        paras.append(l)
    # Un numéro de page peut couper une phrase en deux : on recolle quand le
    # paragraphe précédent n'est pas terminé et que le suivant commence en minuscule.
    merged = []
    for p in paras:
        if merged and p[0].islower() and not re.search(r"[.;:!?]\s*$|\./-$", merged[-1]):
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged


def new_article(numero, titre):
    return {"numero": numero, "titre": titre, "texte_brut": "", "alineas": [],
            "abroge": "(Abrogé)" in titre}


def parse(docx_path):
    paras = read_paragraphs(docx_path)
    livres = [{"numero": "I", "titre_texte": "", "titres": []}]
    livre = titre = chapitre = section = article = alinea = None
    livre = livres[0]
    review = []
    i, n = 0, len(paras)

    def take_title(start):
        """Consomme les lignes MAJUSCULES qui suivent un en-tête (titre descriptif)."""
        j, parts = start, []
        while j < n and RE_CAPS.match(paras[j]) and not any(
            r.match(paras[j]) for r in (RE_LIVRE, RE_TITRE, RE_CHAPITRE, RE_SECTION)
        ) and not paras[j].startswith("ARTICLE"):
            parts.append(paras[j])
            j += 1
        return " ".join(parts), j

    def ensure_chapitre():
        nonlocal chapitre, section
        if chapitre is None:
            chapitre = {"numero": "", "titre": "", "sections": [], "articles": []}
            titre["chapitres"].append(chapitre)
            section = None

    def add_text(line):
        if alinea is not None:
            alinea["texte"] = (alinea["texte"] + "\n" + line).strip()
        elif article is not None:
            article["texte_brut"] = (article["texte_brut"] + "\n" + line).strip()
        else:
            review.append(line)

    # le préambule précède le premier TITRE
    started = False
    while i < n:
        p = paras[i]
        i += 1
        m = RE_LIVRE.match(p)
        if m:
            t, i = take_title(i)
            livre = {"numero": m.group(1), "titre_texte": t, "titres": []}
            livres.append(livre)
            titre = chapitre = section = article = alinea = None
            continue
        m = RE_TITRE.match(p)
        if m:
            started = True
            t, i = take_title(i)
            titre = {"numero": m.group(1), "titre_texte": t, "chapitres": []}
            livre["titres"].append(titre)
            chapitre = section = article = alinea = None
            continue
        if not started:
            continue
        m = RE_CHAPITRE.match(p)
        if m:
            t, i = take_title(i)
            chapitre = {"numero": m.group(1), "titre": t, "sections": [], "articles": []}
            titre["chapitres"].append(chapitre)
            section = article = alinea = None
            continue
        m = RE_SECTION.match(p)
        if m:
            t, i = take_title(i)
            section = {"numero": m.group(1), "titre": t, "articles": []}
            chapitre["sections"].append(section)
            article = alinea = None
            continue
        m = RE_ARTICLES_RANGE.match(p)
        if m:
            ensure_chapitre()
            article = new_article(f"{m.group(1)}-{m.group(2)}", "")
            article["texte_brut"] = m.group(3).strip()
            article["est_plage"] = True
            (section["articles"] if section else chapitre["articles"]).append(article)
            alinea = None
            continue
        m = RE_ARTICLE.match(p)
        if m:
            ensure_chapitre()
            rest = m.group(2).strip()
            article = new_article(m.group(1), "")
            alinea = None
            # "ARTICLE 371.- (1) texte" : alinéa collé à l'en-tête
            ma = RE_ALINEA.match(rest)
            if ma:
                alinea = {"numero": ma.group(1), "texte": ma.group(2).strip()}
                article["alineas"].append(alinea)
            elif len(rest) > 120 or rest.endswith("./-"):
                article["texte_brut"] = rest  # article d'une seule phrase (ex. 372)
            else:
                article["titre"] = rest
                article["abroge"] = "(Abrogé)" in rest
            (section["articles"] if section else chapitre["articles"]).append(article)
            continue
        ma = RE_ALINEA.match(p)
        if ma and article is not None:
            alinea = {"numero": ma.group(1), "texte": ma.group(2).strip()}
            article["alineas"].append(alinea)
            continue
        add_text(p)

    return livres, review


def iter_articles(livres):
    for l in livres:
        for t in l["titres"]:
            for c in t["chapitres"]:
                yield from c["articles"]
                for s in c["sections"]:
                    yield from s["articles"]


def stats(livres):
    ch = [c for l in livres for t in l["titres"] for c in t["chapitres"]]
    arts = list(iter_articles(livres))
    return {
        "livres": len(livres),
        "titres": sum(len(l["titres"]) for l in livres),
        "chapitres": len(ch),
        "sections": sum(len(c["sections"]) for c in ch),
        "articles": len(arts),
        "alineas": sum(len(a["alineas"]) for a in arts),
    }


if __name__ == "__main__":
    livres, review = parse(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump({"code": "Code pénal camerounais", "livres": livres}, f, ensure_ascii=False, indent=2)
    print(stats(livres))
    print("lignes hors article:", len(review))
    for r in review[:10]:
        print("  ", r[:100])
