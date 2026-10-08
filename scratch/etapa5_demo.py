# -*- coding: utf-8 -*-
"""ETAPA 5 — Demonstração da reconciliação com 2 scanners reais + Reconciler.

Para cada código de uma página, executa:
  scanner_regional (grid de regiões)  +  scanner_coluna (faixa de coluna)
e reconcilia com core/analysis.Reconciler. Mostra status por código,
destacando CONFLITO / NÃO_DETERMINADO / PARTIAL (subset).
"""
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from etapa4_harness import (BASE, _load_page, detect_anchors,
                            scanner_regional, scanner_coluna)

from core.analysis import Anchor, Candidate, Evidence, Reconciler, BBox, WEIGHTS


def build_weights(method, price_anchor, code_anchor):
    """Evidências com NEGATIVAS por geometria real (distância/cruzamento).
    Concordância entre scanners NÃO cria verdade: geometria fraca mantém baixo."""
    ev = [Evidence("preco_valido", method, 1, weight=WEIGHTS["preco_valido"]),
          Evidence("mesma_regiao", method, 1, weight=WEIGHTS["mesma_regiao"])]
    d = price_anchor.bbox.centroid_dist_to(code_anchor.bbox)
    if d <= 60:
        ev.append(Evidence("distancia_muito_curta", method, 1, weight=WEIGHTS["distancia_muito_curta"]))
    elif d <= 200:
        ev.append(Evidence("distancia_curta", method, 1, weight=WEIGHTS["distancia_curta"]))
    elif d <= 300:
        ev.append(Evidence("estrutura_ambigua", method, 1, weight=WEIGHTS["estrutura_ambigua"]))
    else:
        ev.append(Evidence("distancia_longa", method, 1, weight=WEIGHTS["distancia_longa"]))
    return ev


def demo(pdf, page, label):
    elements, tables, rects = _load_page(pdf, page)
    prices, codes = detect_anchors(elements, page)
    print(f"\n===== {label} | elems={len(elements)} preços={len(prices)} códigos={len(codes)}")

    reg = scanner_regional(page, elements, codes, prices)
    col = scanner_coluna(page, elements, codes, prices)

    r = Reconciler()
    assocs = []
    code_anchor = {a.value: a for a in codes}
    for code in sorted({c.value for c in codes}):
        cands = []
        ca = code_anchor[code]
        if code in reg:
            c = Candidate("regional_cell", code, page, reg[code])
            nearest = min(reg[code], key=lambda p: p.bbox.centroid_dist_to(ca.bbox))
            c.evidences = build_weights("regional_cell", nearest, ca)
            c.preliminary_score = 1.0
            cands.append(c)
        if code in col:
            c = Candidate("coluna_banda", code, page, col[code])
            nearest = min(col[code], key=lambda p: p.bbox.centroid_dist_to(ca.bbox))
            c.evidences = build_weights("coluna_banda", nearest, ca)
            c.preliminary_score = 0.7
            cands.append(c)
        if not cands:
            assocs.append(r.reconcile(code, page, []))
            continue
        assoc = r.reconcile(code, page, cands)
        assocs.append(assoc)

    ordem = f"{label.split()[0]} {label.split()[-1]}"
    statuses = {}
    for a in assocs:
        statuses[a.status] = statuses.get(a.status, 0) + 1
        pre = ";".join(sorted({str(p.value).replace(".", ",") for p in a.prices}))
        print(f"  {a.codes[0]:>10} -> {pre or 'SEM_PRECO':<24} {a.status:<15} conf={a.confidence:>4.0f}  {a.note[:60]}")
    print(f"  [status] {statuses}")

    r.stamp_shared_notes(assocs)
    grp = r.shared_price_groups(assocs)
    if grp:
        print(f"  [N->1 preços compartilhados] " +
              "; ".join(f"{', '.join(c[:8])}" for c in grp.values()))


def main():
    avon = os.path.join(BASE, "AVON CICLO 15.pdf")
    casa = os.path.join(BASE, "AVON CASA CICLO 15.pdf")
    ely = next((x for x in glob.glob(os.path.join(BASE, "*.pdf"))
                if "elyssence" in os.path.basename(x).lower()), None)
    demo(avon, 65, "avon p65")
    demo(avon, 7, "avon p7")
    demo(casa, 22, "casa p22")
    demo(ely, 3, "elyssence p3")


if __name__ == "__main__":
    main()