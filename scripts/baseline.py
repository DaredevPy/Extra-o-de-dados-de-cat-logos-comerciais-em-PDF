# -*- coding: utf-8 -*-
"""Executa o extrator atual sobre todos os PDFs reais e registra métricas de baseline (sem alterar regras)."""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.pdf_extractor import PDFDocumentReader
from core.parser import CatalogParser

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "baseline")
os.makedirs(OUT_DIR, exist_ok=True)


def classify(p):
    has_code = bool(p.code and p.code.strip())
    has_desc = bool(p.description and p.description.strip())
    has_price = bool(p.price and p.price.strip()) and p.price != "-"
    if has_code and has_desc and has_price:
        return "codigo+desc+preco"
    if has_code and has_desc:
        return "codigo+desc"
    if has_code and has_price:
        return "codigo+preco"
    if has_code:
        return "somente codigo"
    return "incompleto"


for pdf_path in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "*.pdf"))):
    name = os.path.basename(pdf_path)
    if name == "catalogo_exemplo.pdf":
        continue
    print(f"\n##### {name} #####")
    try:
        reader = PDFDocumentReader(pdf_path)
        reader.load_document()
    except Exception as e:
        print(f"ERRO ao abrir: {e}")
        continue

    products = CatalogParser().parse_document(reader.pages_data)

    per_page = Counter(p.page for p in products)
    pages_with = sorted(per_page)
    pages_without = [i for i in range(1, reader.total_pages + 1) if i not in per_page]

    completeness = Counter(classify(p) for p in products)

    prices = sum(1 for p in products if p.price and p.price != "-")
    codes = len({p.code for p in products if p.code})

    result = {
        "arquivo": name,
        "paginas": reader.total_pages,
        "registros": len(products),
        "codigos_unicos": codes,
        "precos_preenchidos": prices,
        "completude": dict(completeness),
        "paginas_com_resultado": len(pages_with),
        "paginas_sem_resultado": len(pages_without),
        "paginas_sem_resultado_amostra": pages_without[:30],
        "paginas_mais_produtivas": per_page.most_common(10),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out = os.path.join(OUT_DIR, name.replace(" ", "_").replace("(", "").replace(")", "") + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"> salvo em {out}")
    # Amostra de registros por página
    sample = defaultdict(list)
    for p in products:
        if len(sample[p.page]) < 2:
            sample[p.page].append(f"{p.code} | {str(p.description or '')[:40]} | {p.price} | {p.status}")
    for pg in sorted(sample)[:8]:
        for s in sample[pg]:
            print(f"  p{pg}: {s}")
