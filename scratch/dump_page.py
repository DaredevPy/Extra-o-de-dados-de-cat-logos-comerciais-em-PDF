# -*- coding: utf-8 -*-
"""Dump detalhado de palavras/rects/lines de uma página, agrupado por linha física."""
import glob
import os
import sys
import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def dump(pdf, pno, ymin=0, ymax=1e9, xmin=0, xmax=1e9):
    with pdfplumber.open(pdf) as p:
        page = p.pages[pno - 1]
        words = [w for w in page.extract_words()
                 if ymin <= w["top"] <= ymax and xmin <= w["x0"] <= xmax]
        words.sort(key=lambda w: (round(w["top"] / 5), w["x0"]))
        lines = {}
        for w in words:
            lines.setdefault(round(w["top"] / 5), []).append(w)
        print(f"n_words={len(words)} rects={len(page.rects)}")
        print("-- RECTS --")
        for r in page.rects[:40]:
            print(f"  rect x0={r['x0']:.0f} x1={r['x1']:.0f} top={r['top']:.0f} bot={r['bottom']:.0f}")
        print("-- WORDS por linha física --")
        for k in sorted(lines):
            row = " | ".join(f"{w['text']}({w['x0']:.0f},{w['top']:.0f})" for w in lines[k])
            if row:
                print(f"  y~{k*5}: {row}")


if __name__ == "__main__":
    which = os.environ.get("PAGE", "av65")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if which == "av65":
        dump(os.path.join(base, "AVON CICLO 15.pdf"), 65)
    elif which == "av7":
        dump(os.path.join(base, "AVON CICLO 15.pdf"), 7)
    elif which == "casa22":
        dump(os.path.join(base, "AVON CASA CICLO 15.pdf"), 22)
    elif which == "casa34":
        dump(os.path.join(base, "AVON CASA CICLO 15.pdf"), 34)
    elif which == "oui3":
        dump(os.path.join(base, "catalogo_oui_202617 (2).pdf"), 3)
    elif which == "ely3":
        f = [x for x in glob.glob(os.path.join(base, "*.pdf"))
             if "elyssence" in os.path.basename(x).lower()]
        dump(f[0], 3)