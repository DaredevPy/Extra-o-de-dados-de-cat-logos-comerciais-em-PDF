# -*- coding: utf-8 -*-
"""ETAPA 3 — Protótipo espacial: inventário geométrico de páginas reais problemáticas.

Nenhum código do parser principal é alterado aqui. Objetivo: entender a geometria
de palavras/rects/lines/curves/images, detectar códigos/preços com regex flexíveis
e testar agrupamento em regiões/linhas físicas.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PDFS = {
    "avon_ciclo": "AVON CICLO 15.pdf",
    "avon_casa": "AVON CASA CICLO 15.pdf",
    "eudora": "catalogo_eudora_202616.pdf",
    "boticario": "catalogo_boticario_202614 (1).pdf",
    "oui": "catalogo_oui_202617 (2).pdf",
}
# -- o nome do arquivo Elyssence precisa ser resolvido por glob (encoding) ----
for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "*.pdf")):
    b = os.path.basename(f)
    if b.lower().startswith("cat"):
        continue
    if "elyssence" in b.lower():
        PDFS["elyssence"] = b
        break

TARGETS = [
    ("avon_ciclo", 65, "Esmalte Disney / tiers de preço"),
    ("avon_ciclo", 58, "Pó Compacto / preço + badge MAIS"),
    ("avon_ciclo", 7, "Batom 28 tons / tagline como desc"),
    ("avon_casa", 22, "Meia infantil"),
    ("avon_casa", 34, "Caneca/Taça Disney 2 preços"),
    ("elyssence", 3, "Códigos 4 dígitos"),
    ("oui", 3, "Preços inteiros sem decimais"),
    ("boticario", 15, "Linha inteira promovida a código"),
    ("eudora", 4, "EAN falso + desconto"),
]

RE_CODE = re.compile(r"^(?:\d{4,8}|[A-Za-z]{2,4}[-/]?\d{2,6}|[A-Z0-9]{2,12})$")
RE_PRICE = re.compile(r"(?:R\$\s?)?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?")
RE_CURR = re.compile(r"R\$\s?\d")


def cent(w):
    return (w["x0"] + w["x1"]) / 2.0, (w["top"] + w["bottom"]) / 2.0


def inventory(path, pno):
    out = {}
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[pno - 1]
        out["size"] = (page.width, page.height)
        words = page.extract_words()
        out["n_words"] = len(words)
        out["n_chars"] = len(page.chars)
        out["n_rects"] = len(page.rects)
        out["n_lines"] = len(page.lines)
        out["n_curves"] = len(page.curves)
        out["n_images"] = len(page.images)
        out["n_annots"] = len(page.annots or [])
        tables = page.find_tables()
        out["n_tables"] = len(tables)
        out["tables_bbox"] = [[round(t.bbox[0]), round(t.bbox[1]), round(t.bbox[2]), round(t.bbox[3])] for t in tables][:8]

        price_words = [w for w in words if RE_PRICE.fullmatch(w["text"])]
        price_with_r = [w for w in words if w["text"].startswith("R$")]
        decimal_prices = [w for w in words if re.search(r"[.,]\d{2}$", w["text"])]
        int_prices = [w for w in words if RE_PRICE.fullmatch(w["text"]) and re.fullmatch(r"\d{1,3}(?:\.\d{3})*(?:,?\d{2})?", w["text"]) and w["text"].isdigit() and len(w["text"]) >= 3 and not re.search(r"[.,]", w["text"])]
        code_words = [w for w in words if RE_CODE.fullmatch(w["text"]) and re.search(r"\d", w["text"])]

        out["precos_total"] = len(price_words)
        out["precos_com_r"] = len(price_with_r)
        out["precos_decimais"] = len(decimal_prices)
        out["precos_inteiros"] = len(int_prices)
        out["codigos_candidatos"] = len(code_words)

        def s(w):
            return {
                "t": w["text"], "x0": round(w["x0"], 1), "x1": round(w["x1"], 1),
                "top": round(w["top"], 1), "bot": round(w["bottom"], 1),
                "sz": round(w.get("size", 0), 1),
            }

        out["amostra_precos"] = [s(w) for w in price_with_r[:10]]
        out["amostra_inteiros"] = [s(w) for w in int_prices[:8]]
        out["amostra_codigos"] = [s(w) for w in code_words[:10]]

        # varredura de ordens de magnitude verticais (agrupamento por faixa de 20px)
        bands = Counter(int(w["top"] // 20) for w in words)
        out["faixas_20px_topN"] = bands.most_common(12)

        # texto de exemplo da página (layout False) com primeira ocorrência de preço
        txt = page.extract_text() or ""
        out["texto_len"] = len(txt)
        first = next((l for l in txt.splitlines() if "R$" in l), None)
        out["primeira_linha_R$"] = first[:120] if first else None
        mc = re.search(r"(~R\s?.\s?\d)", " ".join(words[w]["text"] for w in range(min(400, len(words)))))
        out["procurar_R_isolado"] = bool(re.search(r"\bR\b", " ".join(w["text"] for w in words[:400])))

        # quantas vezes o token 'R$' está separado (ex 'R $ 39')
        sep = sum(1 for w in words if re.search(r"^\d{1,3}(?:\.\d{3})*[.,]\d{2}$", w["text"]))
        out["precos_sem_prefixo"] = sep
    return out


def main():
    limit = int(os.environ.get("LIMIT", "999"))
    for key, pno, note in TARGETS[:limit]:
        path = PDFS.get(key)
        if not path:
            print(f"[{key}] arquivo não encontrado"); continue
        apath = os.path.join(os.path.dirname(__file__), "..", path)
        try:
            r = inventory(apath, pno)
        except Exception as e:
            print(f"== {key} p{pno} ({note}) == ERRO: {e}")
            continue
        print(f"== {key} p{pno} ({note}) ==")
        for k in ("size", "n_words", "n_chars", "n_rects", "n_lines", "n_curves",
                  "n_images", "n_annots", "n_tables", "tables_bbox",
                  "precos_total", "precos_com_r", "precos_decimais", "precos_inteiros",
                  "precos_sem_prefixo", "codigos_candidatos", "texto_len",
                  "primeira_linha_R$"):
            print(f"  {k}: {r.get(k)}")
        print("  amostra_precos:", json.dumps(r["amostra_precos"], ensure_ascii=False))
        print("  amostra_codigos:", json.dumps(r["amostra_codigos"], ensure_ascii=False))
        print("  faixas_20px:", r["faixas_20px_topN"])
        print()


if __name__ == "__main__":
    main()