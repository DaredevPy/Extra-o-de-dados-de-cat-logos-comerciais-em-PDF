# -*- coding: utf-8 -*-
"""ETAPA 6 — Executa a pipeline por evidências nos cenários sintéticos A–I
e no caso real J (referência manual do AVON). Compara com a verdade conhecida."""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.pdf_extractor import PDFDocumentReader
from core.pipeline import EvidenceExtractor, _fmt
from core.models import ExtractionConfig
import scripts.generate_synthetic as gen

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYN = os.path.join(BASE, "synthetic")


def load_pages(pdf):
    reader = PDFDocumentReader(pdf)
    reader.load_document()
    return reader.pages_data


def prices_of(assoc):
    return [_fmt(p.value) for p in assoc.prices] if assoc else []


def run_synthetic():
    gen.build()
    pages = load_pages(gen.OUT_PDF)
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    truth = json.load(open(gen.OUT_JSON, encoding="utf-8"))
    n_pass = 0
    n_tot = 0

    by_page = {p.page_number: ex.extract_page(p) for p in pages}

    def assoc_for(pag, code):
        for a in by_page[pag][0]:
            if a.codes and a.codes[0] == code:
                return a
        return None

    results = []
    for pag_raw, spec in sorted(truth.items()):
        pag = int(pag_raw)  # keys do JSON são strings
        label = next(iter(spec))
        checks = spec[label]
        print(f"\n=== Cenário {label} (página {pag}) ===")
        if label == "H":
            # nenhum produto fantasma com preço sem código
            has_ghost = any(a.codes and a.prices for a in by_page[pag][0])
            n_tot += 1
            print(f"  preço sem código -> produtos fantasma? {has_ghost}")
            ok_ = not has_ghost
            n_pass += ok_
            results.append((label, ok_, "sem fantasma" if ok_ else "inventou produto"))
            continue
        for code, expected in checks.items():
            if code.startswith("_"):
                continue
            n_tot += 1
            a = assoc_for(pag, code)
            got = prices_of(a)
            if label == "C":
                # tiers: 4 preços com quantidade
                tiers = {pv: q for pv, q in expected}
                ok_ = (len(got) == 4 and {pv: None for pv in got and [1]})
                exp_vals = [f"{(v, q)}" for v, q in expected]
                got_qt = {_fmt(p.value): p.quantity for p in a.prices} if a else {}
                ok_ = got_qt and all(got_qt.get(v) == q for v, q in expected)
                print(f"  {code} -> {sorted(got_qt.items())} esperado={sorted({v: q for v, q in expected}.items())} "
                      f"{'PASS' if ok_ else 'FAIL'}")
                n_pass += ok_
                results.append((label, ok_, f"tiers {got_qt}" if ok_ else f"esperado {expected}"))
                continue
            if label in ("A", "B", "D", "E", "G", "I"):
                ok_ = a is not None and sorted(got) == sorted(expected)
                status = a.status if a else "--"
                print(f"  {code} -> {sorted(got) or '(sem preço)'} [{status}] esperado={sorted(expected)} "
                      f"{'PASS' if ok_ else 'FAIL'}")
                n_pass += ok_
                results.append((label, ok_, f"{code}:{got}:{status} vs {expected}"))
                continue
            if label == "F":
                must_conflict = checks.get("_conflito")
                ok_ = a is not None and a.status == "CONFLITO" and ("39,90" in got)
                print(f"  {code} -> {got} [{a.status if a else '--'}] esperado=CONFLITO c/ 39,90 "
                      f"{'PASS' if ok_ else 'FAIL'}  | {a.note if a else '-'}")
                n_pass += ok_
                results.append((label, ok_, a.note if a else "sempre conflito"))
                continue
        n_tot += 1
        if "B" in label:
            grupo = None
            a1, a2 = assoc_for(pag, "200001"), assoc_for(pag, "200002")
            if a1 and a2 and a1.prices and a2.prices and a1.prices[0].value == a2.prices[0].value:
                grupo = True
            print(f"  N->1 (2 códigos/1 preço) {'PASS' if grupo else 'FAIL'}")
            n_pass += grupo if grupo else False
            results.append((label, bool(grupo), "2 códigos -> mesmo preço" if grupo else "não agrupou"))

    print("\n" + "=" * 50)
    print(f"RESULTADO SINTÉTICO: {n_pass}/{n_tot}")
    for (l, ok, d) in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {l}: {d}")
    return n_pass, n_tot


BASELINE_J = {"total": 119, "cod": 119, "preco": 103, "desc": 33}


def main():
    n_pass, n_tot = run_synthetic()
    print("\n### CASO REAL (J) — AVON CICLO 15 vs referência manual ###")
    from scripts import evaluate
    ev = evaluate.main(mode="evidence")
    print(f"  evidência: preço_OK={ev['preco_correto']}/{ev['itens_referencia']} "
          f"desc_OK={ev['descricao_correta']}/{ev['itens_referencia']} "
          f"precisão={ev['precisao']} recall={ev['recall']}")
    print(f"  baseline (legado): preço_OK={BASELINE_J['preco']}/{BASELINE_J['total']} "
          f"desc_OK={BASELINE_J['desc']}/{BASELINE_J['total']} "
          f"precisão=1.0 recall=1.0")


if __name__ == "__main__":
    main()