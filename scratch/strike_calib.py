# -*- coding: utf-8 -*-
"""Caracteriza os traços diagonais sobre preços para calibrar o detector."""
import re
import sys
import glob
import pdfplumber

RE_MONEY = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def seg_points(obj, page_h):
    pts = obj.get("pts")
    if pts:
        a, b = pts[0], pts[-1]
        return (a[0], a[1], b[0], b[1])
    x0, x1, top, bottom = obj.get("x0"), obj.get("x1"), obj.get("top"), obj.get("bottom")
    if None in (x0, x1, top, bottom):
        return None
    return (x0, top, x1, bottom)


def crosses(x0, y0, x1, y1, bx0, by0, bx1, by1):
    for i in range(41):
        t = i / 40.0
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if bx0 <= x <= bx1 and by0 <= y <= by1:
            return True
    return False


def probe(path, max_pages=None):
    rows = []
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
                for obj in (getattr(page, kind) or []):
                    p = seg_points(obj, ph)
                    if p:
                        segs.append((kind, p, obj))
            for kind, (sx0, sy0, sx1, sy1), obj in segs:
                dx, dy = abs(sx1 - sx0), abs(sy1 - sy0)
                if dx < 4 or dy < 4:
                    continue
                if not obj.get("stroked", True):
                    continue
                for w in money:
                    wx0, wx1 = w["x0"], w["x1"]
                    wy0, wy1 = w["top"], w["bottom"]
                    if not crosses(sx0, sy0, sx1, sy1, wx0 - 1, wy0 - 1, wx1 + 1, wy1 + 1):
                        continue
                    seg_len = (dx ** 2 + dy ** 2) ** 0.5
                    w_w = wx1 - wx0
                    w_h = wy1 - wy0
                    # cobertura horizontal do token pelo traço (endpoints normalizados)
                    slo, shi = sorted((sx0, sx1))
                    cov = max(0.0, min(shi, wx1) - max(slo, wx0)) / max(w_w, 1e-6)
                    # centro vertical do traço dentro do token?
                    rows.append(dict(
                        page=pno, word=w["text"], kind=kind,
                        wx0=round(wx0, 1), wy0=round(wy0, 1), wx1=round(wx1, 1), wy1=round(wy1, 1),
                        seg=(round(sx0, 1), round(sy0, 1), round(sx1, 1), round(sy1, 1)),
                        dx=round(dx, 1), dy=round(dy, 1), len=round(seg_len, 1),
                        w_w=round(w_w, 1), w_h=round(w_h, 1),
                        ratio=round(seg_len / max(w_w, 1e-6), 2),
                        cov=round(cov, 2),
                        lw=obj.get("linewidth"),
                    ))
                    break
    return rows


if __name__ == "__main__":
    pdfs = sorted(glob.glob(r"*.pdf"))
    if len(sys.argv) > 1:
        pdfs = sys.argv[1:]
    all_rows = []
    for p in pdfs:
        try:
            rs = probe(p)
        except Exception as e:
            print(p, "ERRO", e)
            continue
        print(f"\n=== {p}: {len(rs)} candidatos diagonais ===")
        for r in rs:
            print("   ", r)
        all_rows.extend(rs)
    print(f"\nTOTAL {len(all_rows)}")
