# -*- coding: utf-8 -*-
"""Dump de páginas (palavras + linhas) para entender o padrão de preço riscado."""
import sys
import pdfplumber

PAGES = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["14", "65", "21"])]
y0f, y1f = (float(v) for v in (sys.argv[3].split(",") if len(sys.argv) > 3 else ("0", "10000")))

with pdfplumber.open(sys.argv[1]) as pdf:
    for pno in PAGES:
        page = pdf.pages[pno - 1]
        print(f"==== PAGE {pno} {page.width}x{page.height}")
        for w in sorted(page.extract_words(), key=lambda w: (round(w["top"]), w["x0"])):
            if y0f <= w["top"] <= y1f:
                print(f"  x={w['x0']:7.1f}-{w['x1']:7.1f} y={w['top']:7.1f}-{w['bottom']:7.1f} "
                      f"sz={w.get('size',0):5.1f} {w['text']!r}")
        print("  -- linhas --")
        for ln in (page.lines or []):
            print("   line", {k: ln.get(k) for k in
                              ("x0", "x1", "top", "bottom", "linewidth",
                               "stroking_color", "non_stroking_color")})
        print("  -- curvas (só bounding) --")
        for cv in (page.curves or []):
            print("   curve", {k: cv.get(k) for k in
                               ("x0", "x1", "top", "bottom", "linewidth", "stroking_color")})
