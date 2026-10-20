# -*- coding: utf-8 -*-
"""Sonda: procura traços (diagonais/horizontais) sobre preços nos catálogos reais."""
import re
import sys
import glob
import pdfplumber

RE_MONEY = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def seg_points(obj, page_h):
    """Retorna (x0,y0,x1,y1) em coordenadas de topo (y cresce para baixo)."""
    pts = obj.get("pts")
    if pts:
        a, b = pts[0], pts[-1]
        return (a[0], a[1], b[0], b[1])
    x0, x1 = obj.get("x0"), obj.get("x1")
    top, bottom = obj.get("top"), obj.get("bottom")
    if None in (x0, x1, top, bottom):
        return None
    return (x0, top, x1, bottom)


def seg_crosses_box(x0, y0, x1, y1, bx0, by0, bx1, by1):
    for i in range(41):
        t = i / 40.0
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if bx0 <= x <= bx1 and by0 <= y <= by1:
            return True
    return False


def probe(path, max_pages=None):
    hits = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for pno, page in enumerate(pages, start=1):
            ph = float(page.height)
            words = page.extract_words()
            money = [w for w in words if RE_MONEY.search(w["text"])]
            if not money:
                continue
            segs = []
            for kind in ("lines", "curves", "rects"):
                for obj in (page.extract(kind) if False else getattr(page, kind) or []):
                    p = seg_points(obj, ph)
                    if p:
                        segs.append((kind, p, obj))
            for kind, (sx0, sy0, sx1, sy1), obj in segs:
                dx, dy = abs(sx1 - sx0), abs(sy1 - sy0)
                orient = "DIAG" if (dx >= 4 and dy >= 4) else ("HOR" if dy < 4 else "VER")
                if orient == "VER":
                    continue
                for w in money:
                    if seg_crosses_box(sx0, sy0, sx1, sy1,
                                       w["x0"] - 2, w["top"] - 2, w["x1"] + 2, w["bottom"] + 2):
                        hits.append({
                            "page": pno, "word": w["text"], "orient": orient, "kind": kind,
                            "seg": (round(sx0, 1), round(sy0, 1), round(sx1, 1), round(sy1, 1)),
                            "stroke": bool(obj.get("stroked", True)),
                            "sc": obj.get("stroking_color"), "nsc": obj.get("non_stroking_color"),
                            "lw": obj.get("linewidth"),
                        })
                        break
    return hits


if __name__ == "__main__":
    pdfs = sorted(glob.glob(r"*.pdf"))
    if len(sys.argv) > 1:
        pdfs = sys.argv[1:]
    for p in pdfs:
        try:
            hits = probe(p)
        except Exception as e:
            print(f"{p}: ERRO {e}")
            continue
        diag = [h for h in hits if h["orient"] == "DIAG"]
        hor = [h for h in hits if h["orient"] == "HOR"]
        print(f"\n=== {p}: {len(hits)} traços sobre preço (DIAG={len(diag)} HOR={len(hor)}) ===")
        for h in diag[:25]:
            print("   D", h)
        for h in hor[:10]:
            print("   H", h)
