# -*- coding: utf-8 -*-
"""ETAPA 4 — Harness de demonstração do modelo de evidências em páginas reais.

Pipeline (usando apenas core/analysis):
  inventário -> âncoras -> regiões -> associações -> confiança -> status.
Produz saída rastreável (evidências por associação). NÃO altera core/parser.py.
"""
import glob
import json
import os
import re
import sys

import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis import (Anchor, BBox, PageElement, ConfidenceScorer, Evidence)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RE_VALUE = re.compile(r"(\d{1,3}(?:[.,]\d{3})*[.,]?\d{0,2})")
RE_INT_STRICT = re.compile(r"^\d{1,3}(?:[.,]\d{3})*[.,]\d{2}$")
DIM_MARKERS = ("g", "ml", "pts", "cm", "kg", "mm", "|", "un", "cx")


def _load_page(pdf, pno):
    with pdfplumber.open(pdf) as p:
        page = p.pages[pno - 1]
        words = page.extract_words()
        chars = {id(c): c for c in page.chars}
        elements = []
        for w in words:
            sizes = [c["size"] for c in page.chars
                     if c["x0"] >= w["x0"] - 1 and c["x1"] <= w["x1"] + 1
                     and c["top"] >= w["top"] - 2 and c["bottom"] <= w["bottom"] + 2]
            sz = sum(sizes) / len(sizes) if sizes else 0.0
            elements.append(PageElement("word", w["text"],
                                        BBox(w["x0"], w["top"], w["x1"], w["bottom"]),
                                        size=sz, detector="extract_words"))
        tables = page.find_tables()
        rects = [PageElement("rect", "", BBox(r["x0"], r["top"], r["x1"], r["bottom"]),
                             detector="page.rects") for r in page.rects]
        return elements, tables, rects


def detect_anchors(elements, page):
    codes, prices, quantities = [], [], []
    rows = {}
    for e in elements:
        rows.setdefault(round(e.bbox.y0 / 6), []).append(e)
    r_anchors = []
    rs = [e for e in elements if e.text.startswith("R$")]
    for w in rs:
        val = None
        m = RE_VALUE.search(w.text)
        if m and re.search(r"\d", m.group(1)):
            val = m.group(1)
        if val is None:
            best = None
            for c in elements:
                if c is w or c.text == "R$":
                    continue
                mv = RE_VALUE.fullmatch(c.text)
                if not mv or not re.search(r"\d", c.text):
                    continue
                vgap = abs(c.bbox.cy - w.bbox.cy)
                hgap = c.bbox.x0 - w.bbox.x1
                if vgap <= 18 and -4 <= hgap <= 140:
                    if best is None or (vgap, hgap) < (best[0], best[1]):
                        best = (vgap, hgap, c)
            if best:
                val = best[2].text
        if val is None:
            continue
        ndig = sum(1 for c in val if c.isdigit())
        if ndig < 3 and not re.search(r"[.,]\d{2}", val):
            continue
        a = Anchor("price", val, w.bbox, page, ["price_R$"], 0.6, {"raw": w.text}, [w])
        prices.append(a)
        r_anchors.append(a)
    for e in elements:
        if e.text.startswith("R$"):
            continue
        mv = RE_VALUE.fullmatch(e.text)
        if not mv or not re.search(r"\d", e.text):
            continue
        val = mv.group(1)
        is_dec = RE_INT_STRICT.fullmatch(val) is not None
        is_int = bool(re.fullmatch(r"\d{3,5}", val))
        if not (is_dec or is_int):
            continue
        if sum(1 for c in e.text if c.isdigit()) >= 4 and \
                re.fullmatch(r"[\dA-Za-z-]{4,12}", e.text) and \
                not re.search(r"[.,]", re.sub(r"[\d]", "", e.text)):
            if re.fullmatch(r"[\d-]{4,12}", e.text):
                continue
        near_r = any(abs(a.bbox.cy - e.bbox.cy) <= 25 and a.bbox.x0 - 5 <= e.bbox.x0 <= a.bbox.x1 + 140
                     for a in r_anchors)
        row = next((lst for lst in rows.values() if any(o is e for o in lst)), [])
        near_prom = any(o.text.upper() in ("POR", "CADA", "PAR", "OFF", "ECONOMIZE") for o in row)
        if not (near_r or near_prom):
            continue
        if any(m in row_text(row).lower() for m in DIM_MARKERS) and not near_prom:
            continue
        a = Anchor("price", val, e.bbox, page, ["price_standalone"], 0.5, {"raw": e.text}, [e])
        prices.append(a)
    # códigos
    for e in elements:
        t = e.text
        if "__" in t or "BBEE" in t:
            continue
        row = next((lst for lst in rows.values() if any(o is e for o in lst)), [])
        if any("__" in o.text or "BBEE" in o.text for o in row):
            continue
        if not re.fullmatch(r"(?:\d{4,8}|[A-Z][A-Za-z0-9-]{2,11})", t):
            continue
        if sum(1 for c in t if c.isdigit()) < 4:
            continue
        if re.fullmatch(r"\d{1,2}", t):
            continue
        codes.append(Anchor("code", t, e.bbox, page, ["code_flex"], 0.5, {}, [e]))
    return prices, codes


def row_text(row):
    return " ".join(o.text for o in row)


def numeric(v):
    return float(v.replace(".", "").replace(",", "."))


def scanner_regional(page, elements, codes, prices):
    """Scanner 1: âncoras dentro da célula de região (grid), preço ABAIXO do código."""
    from core.analysis import build_grid_regions, assign_anchors_to_regions
    regions = build_grid_regions(page, elements, codes,
                                 page_width=max(e.bbox.x1 for e in elements) or 1000)
    all_anchors = prices + codes
    assign_anchors_to_regions(regions, all_anchors)
    out = {}
    for r in regions:
        ra_codes = [a for a in r.anchors if a.kind == "code"]
        ra_prices = [a for a in r.anchors if a.kind == "price"]
        if not ra_codes:
            continue
        for c in ra_codes:
            cands = []
            for p in ra_prices:
                if p.bbox.y0 < c.bbox.y1 - 60:
                    continue
                if p.bbox.y0 - c.bbox.y1 > 340:
                    continue
                d = p.bbox.centroid_dist_to(c.bbox)
                cands.append((d, p))
            if not cands:
                continue
            cands.sort(key=lambda t: t[0])
            closest = cands[0]
            bloco = []
            for d, p in cands:
                if abs(p.bbox.cy - closest[1].bbox.cy) <= 60 or \
                   (p.bbox.y0 >= closest[1].bbox.y0 and p.bbox.y0 - closest[1].bbox.y1 <= 45):
                    bloco.append(p)
            out.setdefault(c.value, []).extend(bloco)
    return out


def scanner_coluna(page, elements, codes, prices):
    """Scanner 2: mesma coluna (faixa X dos códigos), vizinho vertical mais próximo."""
    from core.analysis.regions import _column_limits
    bounds = _column_limits((a.bbox.cx for a in codes), 1000, 40)
    out = {}
    for c in codes:
        col = next((lo, hi) for lo, hi in bounds if lo <= c.bbox.cx <= hi)
        cands = []
        for p in prices:
            if p.bbox.x0 < col[0] or p.bbox.x1 > col[1]:
                continue
            if p.bbox.y0 < c.bbox.y1 - 60:
                continue
            if p.bbox.y0 - c.bbox.y1 > 280:   # cap de distância (NÃO ultrapassa bloco)
                continue
            cands.append(p)
        if not cands:
            continue
        cands.sort(key=lambda p: p.bbox.y0 - c.bbox.y1)
        out.setdefault(c.value, []).append(cands[0])
    return out


def build_associations(page, elements, prices, codes):
    from core.analysis import build_grid_regions, assign_anchors_to_regions
    cols = {round(a.bbox.cx, 1) for a in codes}
    regions = build_grid_regions(page, elements, codes, page_width=max(e.bbox.x1 for e in elements) or 1000)
    all_anchors = prices + codes
    assign_anchors_to_regions(regions, all_anchors)

    table_a = []
    for r in regions:
        ra_codes = [a for a in r.anchors if a.kind == "code"]
        ra_prices = [a for a in r.anchors if a.kind == "price"]
        if not ra_codes:
            continue
        # melhor atribuição: preço abaixo do código dentro da região (o mais próximo)
        for c in ra_codes:
            cands = []
            for p in ra_prices:
                if p.bbox.y0 < c.bbox.y1 - 60:
                    continue
                if p.bbox.y0 - c.bbox.y1 > 280:
                    continue
                d = p.bbox.centroid_dist_to(c.bbox)
                cands.append((d, p))
            if not cands:
                continue
            cands.sort(key=lambda t: t[0])
            closest = cands[0]
            sec = None
            for d, p in cands[1:]:
                if abs(p.bbox.y0 - closest[1].bbox.y0) <= 45 and abs(p.bbox.cx - closest[1].bbox.cx) <= 60:
                    pass  # stacked price do mesmo bloco
            bloco = [p for d, p in cands if abs(p.bbox.cy - closest[1].bbox.cy) <= 60 or
                     (p.bbox.y0 >= closest[1].bbox.y0 and p.bbox.y0 - closest[1].bbox.y1 <= 45)]
            table_a.append({
                "code": c.value,
                "cbbox": c.bbox,
                "prices": sorted({p.value: p for p in bloco}.values(), key=lambda x: x.bbox.y0),
                "closest_dist": round(closest[0], 1),
                "region": r.bbox,
            })
    return table_a


def main():
    avon = os.path.join(BASE, "AVON CICLO 15.pdf")
    casa = os.path.join(BASE, "AVON CASA CICLO 15.pdf")
    ely = next((x for x in glob.glob(os.path.join(BASE, "*.pdf"))
                if "elyssence" in os.path.basename(x).lower()), None)
    targets = [(avon, 65, "avon p65"), (avon, 7, "avon p7"),
               (casa, 22, "casa p22"), (ely, 3, "elyssence p3")]
    for pdf, pno, lbl in targets:
        try:
            elements, tables, rects = _load_page(pdf, pno)
            prices, codes = detect_anchors(elements, pno)
            print(f"== {lbl} | elems={len(elements)} prices={len(prices)} codes={len(codes)} ==")
            for a in prices:
                print(f"  P {a.value} x={a.bbox.x0:.0f} y={a.bbox.y0:.0f} [{','.join(a.detectors)}]")
            for a in codes:
                print(f"  C {a.value} x={a.bbox.x0:.0f} y={a.bbox.y0:.0f}")
            assocs = build_associations(pno, elements, prices, codes)
            print("  ASSOCIAÇÕES (propostas):")
            already = set()
            for r in assocs:
                key = r["code"]
                if key in already:
                    continue
                already.add(key)
                ps = ";".join(f"{p.value}@{p.bbox.y0:.0f}" for p in r["prices"])
                print(f"    {r['code']} -> [{ps}] dist={r['closest_dist']}px reg={[round(v,1) for v in (r['region'].x0, r['region'].y0, r['region'].x1, r['region'].y1)]}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERRO {lbl}: {e}")


if __name__ == "__main__":
    main()