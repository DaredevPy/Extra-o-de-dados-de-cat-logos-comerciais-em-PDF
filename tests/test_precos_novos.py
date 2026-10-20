# -*- coding: utf-8 -*-
"""Testes das regras novas de preço:
  * preço riscado (traço diagonal) = PREÇO ANTIGO, nunca o preço atual;
  * preço único de página valendo para dois códigos (rotulado por quantidade);
  * "preço antigo" não concorre com "preço atual" na reconciliação.

Os cenários usam o MESMO formato de PageData que o pdfplumber entrega
(palavras em coordenadas de topo) e traços no formato de `extract_price_strokes`.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis.elements import Anchor, BBox
from core.analysis.strikes import mark_struck_prices, stroke_marks_bbox
from core.models import ExtractionConfig, PageData
from core.pipeline import EvidenceExtractor


def W(text, x0, x1, top, size=11.0, h=None):
    h = h if h is not None else (18.0 if size >= 14 else 12.0)
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + h,
            "width": x1 - x0, "height": h, "size": size, "doctop": top}


def S(x0, y0, x1, y1, linewidth=1.0, color=(0, 0, 0, 1.0)):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "linewidth": linewidth, "color": list(color)}


# --------------------------------------------------------------------------- #
# 1) Geometria do traço
# --------------------------------------------------------------------------- #
def test_stroke_marks_bbox_diagonal_cobre_preco():
    bbox = BBox(65.6, 249.4, 102.5, 265.4)          # token 'R$22,99'
    assert stroke_marks_bbox(bbox, S(66.6, 259.9, 105.8, 249.7))
    # muito curto para riscar a largura toda
    assert not stroke_marks_bbox(bbox, S(80.0, 259.0, 92.0, 251.0))
    # invasor de outra linha (y muito fora)
    assert not stroke_marks_bbox(bbox, S(66.0, 300.0, 106.0, 290.0))
    # decorativo largo demais
    assert not stroke_marks_bbox(bbox, S(20.0, 259.9, 160.0, 249.7))


def test_mark_struck_prices_marca_so_o_riscado():
    struck = Anchor("price", "22,99", BBox(65.6, 249.4, 102.5, 265.4), 14, [], 0.5)
    current = Anchor("price", "17,99", BBox(65.3, 264.3, 116.7, 288.9), 14, [], 0.5)
    n = mark_struck_prices([struck, current], [S(66.6, 259.9, 105.8, 249.7)])
    assert n == 1
    assert struck.meta.get("struck") is True
    assert not current.meta.get("struck")


# --------------------------------------------------------------------------- #
# 2) FIM A FIM — preço antigo vs. atual (Avon: antigo riscado em cima)
# --------------------------------------------------------------------------- #
def _struck_page_words():
    """Produto com preço antigo riscado ACIMA e preço atual ABAIXO."""
    words = [
        W("246952", 82, 126, 200, size=16.0),
        W("R$22,99", 65.6, 102.5, 249.4),
        W("R$17,99", 65.3, 116.7, 264.3),
        W("Guia", 300, 380, 760),
    ]
    return words


def _page(words, no, strokes=()):
    return PageData(no, "", [], words, strokes=list(strokes))


def test_preco_antigo_nao_vira_preco_atual():
    page = _page(_struck_page_words(), 14,
                 strokes=[S(66.6, 259.9, 105.8, 249.7)])
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, _ = ex.run([page])
    assert len(items) == 1
    it = items[0]
    assert it.price == "17,99"
    assert it.price_old == "22,99"
    assert it.price != "22,99"
    # antigo resolvido como contexto (kind='previous'), não como conflito
    assocs, _ = ex.extract_page(page)
    kinds = [p.kind for p in assocs[0].prices]
    assert "previous" in kinds


def test_preco_sem_traco_nao_tem_preco_antigo():
    page = _page(_struck_page_words(), 14, strokes=[])
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, _ = ex.run([page])
    assert all(it.price_old == "" for it in items)


# --------------------------------------------------------------------------- #
# 3) PREÇO ÚNICO DE PÁGINA — dois códigos, um preço rotulado por quantidade
# --------------------------------------------------------------------------- #
def _two_codes_one_price_words():
    """Dois códigos vizinhos com um único preço "2 POR R$24,99" logo abaixo."""
    words = [
        W("263636", 82, 126, 256, size=16.0),
        W("263623", 82, 126, 296, size=16.0),
        # régua de quantidade explícita, abaixo dos códigos e na mesma faixa X
        W("2", 90, 98, 400),
        W("POR", 102, 134, 400),
        W("R$24,99", 100, 154, 400),
        W("Guia", 300, 380, 760),
    ]
    return words


def test_preco_unico_da_pagina_dois_codigos():
    page = _page(_two_codes_one_price_words(), 30)
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, _ = ex.run([page])
    assert len(items) == 2
    assert all(it.price == "24,99" for it in items)


# --------------------------------------------------------------------------- #
# 4) Reconciliador: antigo não concorre com atual
# --------------------------------------------------------------------------- #
def test_reconcile_preco_antigo_nao_conflita():
    from core.analysis.reconcile import Candidate, Reconciler
    bb = BBox(65.6, 249.4, 102.5, 265.4)
    old = Anchor("price", "22,99", bb, 14, ["test"], 0.5, {"struck": True}, [])
    cur = Anchor("price", "17,99", bb, 14, ["test"], 0.5, {}, [])
    cands = [
        Candidate("regional_cell", "246952", 14, [old, cur], preliminary_score=0.9),
        Candidate("coluna_banda", "246952", 14, [cur], preliminary_score=0.9),
    ]
    assoc = Reconciler().reconcile("246952", 14, cands)
    assert assoc.status != "CONFLITO"
    kinds = {p.value: p.kind for p in assoc.prices}
    assert kinds.get(17.99) != "previous"
    assert kinds.get(22.99) == "previous"
