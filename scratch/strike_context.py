# -*- coding: utf-8 -*-
"""Mostra o contexto (palavras próximas) de cada traço diagonal sobre preço."""
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


def probe(path):
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
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
                if dx < 4 or dy < 4 or not obj.get("stroked", True):
                    continue
                hit = None
                for w in money:
                    if crosses(sx0, sy0, sx1, sy1, w["x0"] - 1, w["top"] - 1, w["x1"] + 1, w["bottom"] + 1):
                        hit = w
                        break
                if hit is None:
                    continue
                xs, ys = sorted([sx0, sx1]), sorted([sy0, sy1])
                cx, cy = (xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2
                print(f"\n--- {path} p{pno}: traço {kind} {tuple(round(v,1) for v in (sx0,sy0,sx1,sy1))} "
                      f"sobre '{hit['text']}' (len={(dx**2+dy**2)**0.5:.1f})")
                ctx = [w for w in words
                       if w["x1"] >= xs[0] - 70 and w["x0"] <= xs[1] + 70
                       and w["bottom"] >= ys[0] - 40 and w["top"] <= ys[1] + 40]
                for w in sorted(ctx, key=lambda w: (round(w["top"]), w["x0"])):
                    print(f"     x={w['x0']:7.1f}-{w['x1']:7.1f} y={w['top']:7.1f}-{w['bottom']:7.1f}  {w['text']!r}")


if __name__ == "__main__":
    for p in (sys.argv[1:] or sorted(glob.glob(r"*.pdf"))):
        probe(p)
