# -*- coding: utf-8 -*-
"""Roda o pipeline de evidências em páginas selecionadas e imprime o resultado."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.pdf_extractor import PDFDocumentReader
from core.pipeline import EvidenceExtractor

path = sys.argv[1]
pages = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else None

reader = PDFDocumentReader(path)
reader.load_document()
sel = [p for p in reader.pages_data if not pages or p.page_number in pages]
ex = EvidenceExtractor()
for p in sel:
    items, stats = ex.run([p], include_unpriced=False)
    print(f"\n===== {path} PÁGINA {p.page_number} stats={stats} itens={len(items)}")
    for it in items:
        print(f"  cod={it.code!r:12} var={it.variation!r:22} preco={it.price!r:10} "
              f"extra={it.price_extra!r:8} qtd={it.quantity_prices} "
              f"conf={it.confidence} st={it.status}")
        print(f"      desc={it.description!r}")
        if it.debug:
            print(f"      debug={it.debug[:220]!r}")
