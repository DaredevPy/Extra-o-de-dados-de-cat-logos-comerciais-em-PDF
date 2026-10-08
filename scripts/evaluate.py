# -*- coding: utf-8 -*-
"""Avalia o extrator atual contra a referência manual do catálogo Avon."""
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.pdf_extractor import PDFDocumentReader
from core.parser import CatalogParser
from core.models import ExtractionConfig

REF_PATH = os.path.join(os.path.dirname(__file__), "..", "referencia_avon.json")


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower()


def parse_price(s):
    if not s:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})", s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def main(pdf_path=None, out_json=None, page_filter=None, mode="default"):
    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)

    pdf_path = pdf_path or os.path.join(os.path.dirname(__file__), "..", ref["pdf"])
    reader = PDFDocumentReader(pdf_path)
    reader.load_document()

    cfg = ExtractionConfig()
    if page_filter:
        cfg.page_range = page_filter
    if mode == "evidence":
        from core.pipeline import EvidenceExtractor
        products, _ = EvidenceExtractor(cfg).run(reader.pages_data, include_unpriced=True)
    elif os.environ.get("EVAL_OLD"):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "parser_old", os.path.join(os.path.dirname(__file__), "..", "_old", "parser_old.py")
        )
        parser_old = importlib.util.module_from_spec(spec)
        parser_old.__name__ = "parser_old"
        sys.modules["parser_old"] = parser_old
        spec.loader.exec_module(parser_old)
        products = parser_old.CatalogParser().parse_document(reader.pages_data)
    else:
        parser = CatalogParser(cfg)
        products = parser.parse_document(reader.pages_data)

    # Índices da referência
    ref_by_page = defaultdict(dict)
    for page in ref["paginas"]:
        for it in page["itens"]:
            ref_by_page[page["pagina"]][it["codigo"]] = it

    matched_ref = set()       # (pagina, codigo) encontrados
    fp = []                   # registros sem correspondência na referência
    matched_records = []      # registros com correspondência na referência

    for p in products:
        if p.page not in ref_by_page:
            continue  # avalia somente páginas de validação
        if p.code.strip() in ref_by_page[p.page]:
            matched_ref.add((p.page, p.code.strip()))
            matched_records.append(p)
        else:
            fp.append(p)

    total_ref = sum(len(v) for v in ref_by_page.values())

    # Métricas de associação
    desc_ok = 0
    price_ok = 0
    code_desc_ok = 0
    code_price_ok = 0
    for p in matched_records:
        ref_item = ref_by_page[p.page][p.code.strip()]
        kw = norm(ref_item["descricao"])
        if kw and kw in norm(p.description or ""):
            desc_ok += 1
            code_desc_ok += 1
        pp = parse_price(p.price)
        if pp is not None and any(abs(pp - r) < 0.01 for r in ref_item["precos"]):
            price_ok += 1
            code_price_ok += 1

    n_extracted = len(products)
    n_extracted_ref = len(matched_records) + len(fp)
    n_matched = len(matched_records)
    precision = n_matched / n_extracted_ref if n_extracted_ref else 0.0
    recall = len(matched_ref) / total_ref if total_ref else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    missing = [(pg, c) for pg, items in ref_by_page.items() for c in items if (pg, c) not in matched_ref]
    result_missing = missing[:30]

    result = {
        "faltam_referencia": len(missing),
        "faltam_amostra": result_missing,
        "paginas_processadas": reader.total_pages,
        "registros_gerados": n_extracted,
        "registros_paginas_validacao": n_extracted_ref,
        "itens_referencia": total_ref,
        "codigos_corretos": len(matched_ref),
        "precisao": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "falsos_positivos": len(fp),
        "falsos_negativos": total_ref - len(matched_ref),
        "descricao_correta": desc_ok,
        "preco_correto": price_ok,
        "assoc_codigo_descricao_ok": code_desc_ok,
        "assoc_codigo_preco_ok": code_price_ok,
        "fp_por_pagina": dict(Counter(p.page for p in fp).most_common(15)),
        "produtos_por_pagina": dict(Counter(p.page for p in products).most_common(15)),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result

    print("\nAmostra de falsos positivos:")
    for p in fp[:25]:
        print(f"  p{p.page} code={p.code!r} desc={(p.description or "")[:45]!r} price={p.price!r} src={p.source_type}")
    print("\nAmostra de registros corretos (codigo):")
    for p in matched_records[:10]:
        print(f"  p{p.page} code={p.code!r} desc={(p.description or "")[:45]!r} price={p.price!r}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pages", default=None)
    ap.add_argument("--mode", default="default")
    args = ap.parse_args()
    main(args.pdf, args.out, args.pages, args.mode)
