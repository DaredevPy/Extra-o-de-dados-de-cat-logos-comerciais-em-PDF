# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.test_pagina5 import _banner_page_words, _page, _inventory
from core.pipeline import EvidenceExtractor
from core.models import ExtractionConfig
from core.analysis.commercial import analyze_commercial_region
from core.analysis.strikes import stroke_marks_bbox

page = _page(_banner_page_words(), 65)
ex, elements, prices, codes, page_h = _inventory(page)
for c in codes:
    print("code", c.value, c.bbox)
for p in prices:
    print("price", p.value, p.bbox, "struck", p.meta.get("struck"))
region, promo_ids = analyze_commercial_region(65, elements, codes, prices, page_h)
print("rules", [(r.quantity, r.price) for r in region.price_rules])
print("region.units", [(u.code, u.variation) for u in region.units])
st = ex._structure_scan(page, elements, codes, prices, page_h)
print("st.candidates", list(st.candidates), "tiers", st.tiers)
print("scanners linha", ex._scanner_linha(page))
print("scanners region", ex._scanner_region(page, elements, codes, prices))
print("owners", {k: [a.value for a in v] for k, v in ex._owners(codes, prices).items()})
items, stats = ex.run([page], include_unpriced=True)
for it in items:
    print("ITEM", it.code, it.price, it.debug)
