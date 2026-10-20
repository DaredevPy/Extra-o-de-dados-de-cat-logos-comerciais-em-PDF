# -*- coding: utf-8 -*-
"""Estatística de cores dos traços diagonais sobre preços + preço riscado vs. preço atual."""
import re
import sys
import glob
import collections
import pdfplumber

RE_MONEY = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def seg_points(obj):
    pts = obj.get("pts")
    if pts:
        return (pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
    return (obj.get("x0"), obj.get("top"), obj.get("x1"), obj.get("bottom"))


def crosses(x0, y0, x1, y1, bx0, by0, bx1, by1):
    for i in range(41):
        t = i / 40.0
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if bx0 <= x <= bx1 and by0 <= y <= by1:
            return True
    return False


def color_key(c):
    if isinstance(c, (list, tuple)):
        return "(" + ",".join(f"{v:g}" for v in c) + ")"
    return str(c)


def probe(path):
    stats = collections.Counter()
    for pno, page in enumerate(pdfplumber.open(path).pages, start=1):
        words = page.extract_words()
        money = [w for w in words if RE_MONEY.search(w["text"])]
        if not money:
            continue
        for kind in ("lines", "curves"):
            for obj in (getattr(page, kind) or []):
                p = seg_points(obj)
                if None in p:
                    continue
                x0, y0, x1, y1 = p
                dx, dy = abs(x1 - x0), abs(y1 - y0)
                if dx < 6 or dy < 4 or not obj.get("stroked", True):
                    continue
                for w in money:
                    if crosses(x0, y0, x1, y1, w["x0"], w["top"], w["x1"], w["bottom"]):
                        stats[(kind, color_key(obj.get("stroking_color")),
                               obj.get("linewidth"))] += 1
                        break
    return stats


if __name__ == "__main__":
    for p in (sys.argv[1:] or sorted(glob.glob(r"*.pdf"))):
        print(f"\n=== {p} ===")
        for k, v in probe(p).most_common():
            print(f"  {v:4d}  {k}")
