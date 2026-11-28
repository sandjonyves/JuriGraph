"""Exporte les statistiques de JuriGraph dans un classeur Excel avec graphiques.

Sources lues (aucun appel réseau, aucune connexion Neo4j) :
  - data/reports/eval_recherche.json   (résultats de evaluate_search.py)
  - data/eval/faits_articles.jsonl     (jeu de scénarios)
  - code_penal_structure_docx.json     (corpus)
  - renvois.json                       (renvois entre articles)

Le classeur est régénéré à chaque exécution ; les agrégats (par catégorie,
histogrammes, écarts) sont des formules Excel qui se recalculent.

Usage :
    python scripts/exporter_statistiques.py
    python scripts/exporter_statistiques.py --sortie data/reports/autre.xlsx
    python scripts/exporter_statistiques.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.verifier_gold_set import charger_articles, recouvrement_lexical

SORTIE = RACINE / "data/reports/statistiques_jurigraph.xlsx"
POLICE = "Arial"
CONFIGS_SCENARIO = ["V", "V+PT", "V+PT+R+S", "V+R+S"]
METRIQUES = ["R@5", "R@10", "MRR", "nDCG@10"]
CLASSES_RECOUVREMENT = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]


# --------------------------------------------------------------- préparation des données

def lignes_ablations(rapport: dict) -> list[list]:
    """Une ligne par configuration : métriques dev et test côte à côte."""
    dev, test = rapport["ablations"]["dev"], rapport["ablations"]["test"]
    lignes = []
    for nom in dev:
        d, t = dev[nom], test[nom]
        lignes.append([nom, d["R@10"], t["R@10"], d["MRR"], t["MRR"], d["nDCG@10"],
                       t["nDCG@10"], t["R@5"], t["ic_R@10"][0], t["ic_R@10"][1],
                       t["p_R@10"], t["latence"]])
    return lignes


def lignes_scenarios(rapport: dict, scenarios: list[dict], articles: dict) -> list[list]:
    """Une ligne par scénario, avec recouvrement lexical et résultats par configuration."""
    par_id: dict[str, dict] = {}
    for split in ("dev", "test"):
        for nom in CONFIGS_SCENARIO:
            for ligne in rapport["details"][split].get(nom, []):
                par_id.setdefault(ligne["id"], {})[nom] = ligne
    lignes = []
    for sc in scenarios:
        textes = [articles[n]["texte"] for n in sc["attendus"] if n in articles]
        recouvrement = max((recouvrement_lexical(sc["faits"], t) for t in textes), default=None)
        resultats = par_id.get(sc["id"], {})
        ligne = [sc["id"], sc["split"], sc["categorie"], sc["faits"], ", ".join(sc["attendus"]),
                 ", ".join(sc["acceptables"]), recouvrement]
        for nom in CONFIGS_SCENARIO:
            r = resultats.get(nom)
            ligne += [r["R@10"] if r else None, r["MRR"] if r else None]
        v = resultats.get("V")
        ligne.append(", ".join(v["classement"][:3]) if v else "exclu (sans infraction)")
        lignes.append(ligne)
    return lignes


def lignes_corpus(chemin_corpus: Path) -> list[list]:
    """Nombre d'articles par titre du Livre II."""
    donnees = json.loads(chemin_corpus.read_text(encoding="utf-8"))

    def compter(noeud: dict) -> int:
        total = len(noeud.get("articles", []))
        for cle, valeur in noeud.items():
            if isinstance(valeur, list) and cle not in ("articles", "alineas"):
                total += sum(compter(e) for e in valeur if isinstance(e, dict))
        return total

    lignes = []
    for livre in donnees["livres"]:
        for titre in livre.get("titres", []):
            libelle = (titre.get("titre_texte") or "").strip().capitalize()
            lignes.append([f"Livre {livre['numero']} — Titre {titre.get('numero', '')}",
                           libelle[:70], compter(titre)])
    return lignes


def lignes_renvois(chemin: Path, articles: dict, n: int = 15) -> list[list]:
    """Articles les plus souvent cités par d'autres articles."""
    renvois = json.loads(chemin.read_text(encoding="utf-8"))
    compte = Counter(str(r["cible"]) for r in renvois)
    return [[f"Art. {num}", articles.get(num, {}).get("titre", ""), c]
            for num, c in compte.most_common(n)]


# --------------------------------------------------------------- mise en forme

def _styles():
    """Styles communs (import différé d'openpyxl)."""
    from openpyxl.styles import Alignment, Font, PatternFill
    return {"normal": Font(name=POLICE, size=10),
            "entete": Font(name=POLICE, size=10, bold=True, color="FFFFFF"),
            "titre": Font(name=POLICE, size=14, bold=True),
            "note": Font(name=POLICE, size=9, italic=True, color="555555"),
            "fond_entete": PatternFill("solid", fgColor="1F4E78"),
            "habillage": Alignment(wrap_text=True, vertical="top")}


def ecrire_tableau(ws, ligne0: int, entetes: list[str], lignes: list[list],
                   formats: dict[int, str] | None = None) -> int:
    """Écrit un tableau (en-tête + lignes) ; renvoie le numéro de la dernière ligne."""
    st = _styles()
    for j, entete in enumerate(entetes, 1):
        cell = ws.cell(row=ligne0, column=j, value=entete)
        cell.font, cell.fill = st["entete"], st["fond_entete"]
        cell.alignment = st["habillage"]
    for i, ligne in enumerate(lignes, ligne0 + 1):
        for j, valeur in enumerate(ligne, 1):
            cell = ws.cell(row=i, column=j, value=valeur)
            cell.font = st["normal"]
            if formats and j in formats:
                cell.number_format = formats[j]
    return ligne0 + len(lignes)


def ajuster_colonnes(ws, largeurs: dict[str, float]) -> None:
    """Fixe la largeur des colonnes."""
    for colonne, largeur in largeurs.items():
        ws.column_dimensions[colonne].width = largeur


def graphique_barres(titre: str, titre_y: str, ws, col_cat: int, cols_val: list[int],
                     ligne_entete: int, ligne_fin: int, ancre: str, horizontal: bool = False,
                     hauteur: float = 8.0, largeur: float = 18.0, y_max: float | None = 1.0):
    """Ajoute un graphique en barres natif Excel."""
    from openpyxl.chart import BarChart, Reference
    chart = BarChart()
    chart.type = "bar" if horizontal else "col"
    chart.title, chart.y_axis.title = titre, titre_y
    chart.height, chart.width = hauteur, largeur
    chart.roundedCorners = False
    for col in cols_val:
        donnees = Reference(ws, min_col=col, min_row=ligne_entete, max_row=ligne_fin)
        chart.add_data(donnees, titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=col_cat, min_row=ligne_entete + 1, max_row=ligne_fin))
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    if y_max is not None:
        chart.y_axis.scaling.min, chart.y_axis.scaling.max = 0, y_max
    chart.x_axis.tickLblSkip = 1
    if horizontal:
        chart.x_axis.scaling.orientation = "maxMin"
    if len(cols_val) == 1:
        chart.legend = None
    elif chart.legend is not None:
        chart.legend.position = "b"
        chart.legend.overlay = False
    ws.add_chart(chart, ancre)
    return chart


# --------------------------------------------------------------- feuilles

def feuille_lisez_moi(wb, rapport: dict) -> None:
    """Feuille d'explication."""
    st = _styles()
    ws = wb.active
    ws.title = "Lisez-moi"
    lignes = [
        ("JuriGraph — statistiques d'évaluation", st["titre"]),
        (f"Date des résultats : {rapport['date']}", st["normal"]),
        (("STATUT : PROVISOIRE — jeu de scénarios rédigé par l'IA, non encore validé par "
         "l'utilisateur."), Font_rouge()),
        ("", st["normal"]),
        ("Feuilles :", st["normal"]),
        ("• Ablations : métriques de chaque configuration de recherche, dev et test, avec graphiques.",
         st["normal"]),
        ("• Réglage : configurations réglées sur dev et mesurées sur test.", st["normal"]),
        ("• Scénarios : résultat scénario par scénario (filtrable), recouvrement lexical.",
         st["normal"]),
        ("• Par catégorie : moyennes par catégorie (formules), graphique.", st["normal"]),
        ("• Recouvrement : distribution du recouvrement lexical faits/loi (formules), graphique.",
         st["normal"]),
        ("• Corpus : articles par titre et articles les plus cités par renvoi.", st["normal"]),
        ("• Essais réglage : toutes les combinaisons de la grille testées sur dev.", st["normal"]),
        ("", st["normal"]),
        ("Glossaire :", st["normal"]),
        (("• V = vectorielle, PT = plein texte, R = renvois, S = voisins de section, "
         "MQ = multi-requêtes."), st["normal"]),
        (("• R@10 = part des articles attendus trouvés dans les 10 premiers ; MRR = 1 / rang du "
         "premier attendu ; nDCG@10 = qualité de l'ordre (1 = parfait)."), st["normal"]),
        (("• IC95 = intervalle de confiance à 95 % (bootstrap) ; p = test de permutation apparié "
         "contre V (p < 0,05 : différence significative)."), st["normal"]),
        ("", st["normal"]),
        (f"Effectifs : dev = {rapport['n_dev']} scénarios évaluables, test = {rapport['n_test']}.",
         st["normal"]),
        (("Sources : data/reports/eval_recherche.json (evaluate_search.py), "
         "data/eval/faits_articles.jsonl, code_penal_structure_docx.json, renvois.json."),
         st["note"]),
        ("Régénérer : python scripts/exporter_statistiques.py", st["note"]),
    ]
    for i, (texte, police) in enumerate(lignes, 1):
        ws.cell(row=i, column=1, value=texte).font = police
    ajuster_colonnes(ws, {"A": 120})


def Font_rouge():
    """Police d'avertissement."""
    from openpyxl.styles import Font
    return Font(name=POLICE, size=10, bold=True, color="C00000")


def feuille_ablations(wb, rapport: dict) -> None:
    """Tableau des ablations et graphiques."""
    ws = wb.create_sheet("Ablations")
    entetes = ["Configuration", "R@10 dev", "R@10 test", "MRR dev", "MRR test", "nDCG@10 dev",
               "nDCG@10 test", "R@5 test", "IC95 bas R@10 test", "IC95 haut R@10 test",
               "p R@10 test (vs V)", "Latence test (ms)", "Écart R@10 test vs V",
               "Écart MRR test vs V"]
    lignes = lignes_ablations(rapport)
    fin = ecrire_tableau(ws, 1, entetes, lignes,
                         {j: "0.000" for j in range(2, 12)} | {12: "0"})
    for i in range(2, fin + 1):
        ws.cell(row=i, column=13, value=f"=C{i}-$C$2").number_format = "+0.000;-0.000;0.000"
        ws.cell(row=i, column=14, value=f"=E{i}-$E$2").number_format = "+0.000;-0.000;0.000"
        for j in (13, 14):
            ws.cell(row=i, column=j).font = _styles()["normal"]
    ws.cell(row=fin + 2, column=1,
            value="Écarts calculés par rapport à la ligne V (ligne 2). Valeurs : "
                  "evaluate_search.py, paramètres par défaut.").font = _styles()["note"]
    ajuster_colonnes(ws, {"A": 16} | {c: 11 for c in "BCDEFGHIJKLMN"})
    ws.freeze_panes = "B2"
    graphique_barres("Recall@10 par configuration", "Recall@10", ws, 1, [2, 3], 1, fin, "A16")
    graphique_barres("MRR par configuration", "MRR", ws, 1, [4, 5], 1, fin, "J16")


def feuille_reglage(wb, rapport: dict) -> None:
    """Configurations réglées sur dev, mesurées sur test."""
    ws = wb.create_sheet("Réglage")
    reglage, final = rapport.get("reglage", {}), rapport.get("final", {})
    entetes = ["Configuration", "k_rrf", "poids plein texte", "poids graphe", "R@10 dev",
               "R@10 test", "MRR dev", "MRR test", "nDCG@10 test", "p R@10 test (vs V)"]
    lignes = []
    for nom, mesures_test in final.get("test", {}).items():
        base = nom.replace(" (réglée)", "")
        cfg = reglage.get(base, {}).get("config", {})
        d = final["dev"][nom]
        lignes.append([nom, cfg.get("k_rrf", "défaut"), cfg.get("poids_plein_texte", "—"),
                       cfg.get("poids_graphe", "—"), d["R@10"], mesures_test["R@10"], d["MRR"],
                       mesures_test["MRR"], mesures_test["nDCG@10"], mesures_test["p_R@10"]])
    fin = ecrire_tableau(ws, 1, entetes, lignes, {j: "0.000" for j in range(5, 11)})
    ajuster_colonnes(ws, {"A": 22} | {c: 12 for c in "BCDEFGHIJ"})
    if lignes:
        graphique_barres("Configurations réglées : Recall@10 et MRR (test)", "Valeur", ws, 1,
                         [6, 8], 1, fin, "A10")


def feuille_scenarios(wb, lignes: list[list]) -> int:
    """Détail par scénario ; renvoie la dernière ligne."""
    ws = wb.create_sheet("Scénarios")
    entetes = ["id", "split", "catégorie", "faits", "attendus", "acceptables",
               "recouvrement lexical"]
    for nom in CONFIGS_SCENARIO:
        entetes += [f"R@10 {nom}", f"MRR {nom}"]
    entetes.append("3 premiers (V)")
    fin = ecrire_tableau(ws, 1, entetes, lignes, {j: "0.00" for j in range(7, 16)})
    for i in range(2, fin + 1):
        ws.cell(row=i, column=4).alignment = _styles()["habillage"]
    ajuster_colonnes(ws, {"A": 6, "B": 6, "C": 18, "D": 60, "E": 11, "F": 11, "G": 11}
                     | {c: 9 for c in "HIJKLMNO"} | {"P": 18})
    ws.auto_filter.ref = f"A1:P{fin}"
    ws.freeze_panes = "E2"
    return fin


def feuille_categories(wb, scenarios: list[dict], fin_sc: int) -> None:
    """Moyennes par catégorie, en formules sur la feuille Scénarios."""
    ws = wb.create_sheet("Par catégorie")
    categories = sorted({s["categorie"] for s in scenarios if s["attendus"]})
    entetes = ["Catégorie", "Scénarios évaluables", "R@10 V", "MRR V", "R@10 V+PT+R+S",
               "R@10 V+R+S", "Recouvrement moyen"]
    ecrire_tableau(ws, 1, entetes, [[c] for c in categories])
    plage = f"$C$2:$C${fin_sc}"

    def moyenne(col: str, ligne: int) -> str:
        return (f'=IFERROR(AVERAGEIFS(\'Scénarios\'!${col}$2:${col}${fin_sc},'
                f"'Scénarios'!{plage},$A{ligne}),\"\")")

    for i in range(2, len(categories) + 2):
        ws.cell(row=i, column=2,
                value=f"=COUNTIFS('Scénarios'!{plage},$A{i},'Scénarios'!$H$2:$H${fin_sc},\"<>\")")
        for j, col in ((3, "H"), (4, "I"), (5, "L"), (6, "N"), (7, "G")):
            cell = ws.cell(row=i, column=j, value=moyenne(col, i))
            cell.number_format = "0.00"
        for j in range(2, 8):
            ws.cell(row=i, column=j).font = _styles()["normal"]
    fin = len(categories) + 1
    ws.cell(row=fin + 2, column=1,
            value="Formules sur la feuille Scénarios, splits dev et test réunis. "
                  "Les petites catégories (n = 1 ou 2) sont peu fiables.").font = _styles()["note"]
    ajuster_colonnes(ws, {"A": 22} | {c: 14 for c in "BCDEFG"})
    graphique_barres("Recall@10 par catégorie (dev + test)", "Recall@10", ws, 1, [3, 5, 6],
                     1, fin, "A13")


def feuille_recouvrement(wb, fin_sc: int) -> None:
    """Histogramme du recouvrement lexical, en formules."""
    ws = wb.create_sheet("Recouvrement")
    entetes = ["Classe", "Borne basse", "Borne haute", "Nombre de scénarios"]
    bornes = list(zip(CLASSES_RECOUVREMENT, CLASSES_RECOUVREMENT[1:] + [1.01]))
    lignes = [[f"{b:.2f} – {h:.2f}" if h <= 1 else f"≥ {b:.2f}", b, h] for b, h in bornes]
    fin = ecrire_tableau(ws, 1, entetes, lignes, {2: "0.00", 3: "0.00"})
    plage = f"'Scénarios'!$G$2:$G${fin_sc}"
    for i in range(2, fin + 1):
        cell = ws.cell(row=i, column=4,
                       value=f'=COUNTIFS({plage},">="&B{i},{plage},"<"&C{i})')
        cell.font = _styles()["normal"]
    ws.cell(row=fin + 1, column=1, value="Total").font = _styles()["normal"]
    ws.cell(row=fin + 1, column=4, value=f"=SUM(D2:D{fin})").font = _styles()["normal"]
    ws.cell(row=fin + 2, column=1, value="Médiane").font = _styles()["normal"]
    ws.cell(row=fin + 2, column=4, value=f"=MEDIAN({plage})").number_format = "0.00"
    ws.cell(row=fin + 4, column=1,
            value="Recouvrement = part des racines de mots des faits présentes dans l'article "
                  "attendu (scripts/verifier_gold_set.py). Seuil d'alerte : 0,5.").font = _styles()["note"]
    ajuster_colonnes(ws, {"A": 14, "B": 12, "C": 12, "D": 20})
    graphique_barres("Distribution du recouvrement lexical faits / loi", "Scénarios", ws, 1, [4],
                     1, fin, "F2", y_max=None)


def feuille_corpus(wb, corpus: list[list], renvois: list[list]) -> None:
    """Statistiques du corpus et des renvois."""
    ws = wb.create_sheet("Corpus")
    fin1 = ecrire_tableau(ws, 1, ["Titre", "Intitulé", "Articles"], corpus)
    ws.cell(row=fin1 + 1, column=1, value="Total").font = _styles()["normal"]
    ws.cell(row=fin1 + 1, column=3, value=f"=SUM(C2:C{fin1})").font = _styles()["normal"]
    debut2 = fin1 + 4
    fin2 = ecrire_tableau(ws, debut2, ["Article cible", "Titre de l'article", "Renvois reçus"],
                          renvois)
    ajuster_colonnes(ws, {"A": 22, "B": 60, "C": 14})
    graphique_barres("Articles par titre", "Articles", ws, 1, [3], 1, fin1, "E2",
                     horizontal=True, hauteur=10, y_max=None)
    graphique_barres("Articles les plus cités par renvoi", "Renvois reçus", ws, 1, [3], debut2,
                     fin2, "E24", horizontal=True, hauteur=14, y_max=None)


def feuille_essais(wb, rapport: dict) -> None:
    """Toutes les combinaisons de la grille de réglage (dev)."""
    ws = wb.create_sheet("Essais réglage")
    lignes = []
    for nom, bloc in rapport.get("reglage", {}).items():
        for e in bloc["essais"]:
            lignes.append([nom, e.get("k_rrf"), e.get("poids_plein_texte"), e.get("poids_graphe"),
                           e.get("profondeur"), e["R@5"], e["R@10"], e["MRR"], e["nDCG@10"]])
    fin = ecrire_tableau(ws, 1, ["Configuration", "k_rrf", "poids plein texte", "poids graphe",
                                 "profondeur", "R@5 dev", "R@10 dev", "MRR dev", "nDCG@10 dev"],
                         lignes, {j: "0.000" for j in range(6, 10)})
    ws.auto_filter.ref = f"A1:I{max(fin, 1)}"
    ajuster_colonnes(ws, {"A": 14} | {c: 12 for c in "BCDEFGHI"})


# --------------------------------------------------------------- assemblage

def construire_classeur(rapport: dict, scenarios: list[dict], articles: dict,
                        corpus: list[list], renvois: list[list]):
    """Assemble le classeur complet."""
    from openpyxl import Workbook
    wb = Workbook()
    feuille_lisez_moi(wb, rapport)
    feuille_ablations(wb, rapport)
    feuille_reglage(wb, rapport)
    fin_sc = feuille_scenarios(wb, lignes_scenarios(rapport, scenarios, articles))
    feuille_categories(wb, scenarios, fin_sc)
    feuille_recouvrement(wb, fin_sc)
    feuille_corpus(wb, corpus, renvois)
    feuille_essais(wb, rapport)
    return wb


def main() -> int:
    """Point d'entrée."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resultats", default=str(RACINE / "data/reports/eval_recherche.json"))
    parser.add_argument("--scenarios", default=str(RACINE / "data/eval/faits_articles.jsonl"))
    parser.add_argument("--sortie", default=str(SORTIE))
    parser.add_argument("--dry-run", action="store_true", help="n'écrit aucun fichier")
    args = parser.parse_args()

    rapport = json.loads(Path(args.resultats).read_text(encoding="utf-8"))
    scenarios = [json.loads(ligne) for ligne in
                 Path(args.scenarios).read_text(encoding="utf-8").splitlines() if ligne.strip()]
    articles = charger_articles(RACINE / "code_penal_structure_docx.json")
    corpus = lignes_corpus(RACINE / "code_penal_structure_docx.json")
    renvois = lignes_renvois(RACINE / "renvois.json", articles)
    if args.dry_run:
        print(f"[dry-run] {len(rapport['ablations']['dev'])} configurations, "
              f"{len(scenarios)} scénarios, {len(corpus)} titres, {len(renvois)} cibles de renvoi.")
        return 0
    wb = construire_classeur(rapport, scenarios, articles, corpus, renvois)
    sortie = Path(args.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    wb.save(sortie)
    print(f"Classeur écrit : {sortie} ({', '.join(wb.sheetnames)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
