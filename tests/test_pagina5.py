# -*- coding: utf-8 -*-
"""
Testes da missão "Página 5" (região comercial estrutural da AVON CASA CICLO 15).

Cobre: (1) interpretação estrutural — código + variação + descrição
compartilhada + preço por quantidade (1/2/3 POR) + promoção em bloco separado;
(2) a guarda anti-regressão — UMA regra isolada ("2 POR R$6,99" de banner
combinatório) NÃO pode virar preço de produto; (3) o caso real do PDF.

Os leiautes sintéticos imitam a geometria da página 5 real (coluna de códigos à
esquerda, painel de regras/descrição no centro, promoção à direita) sem
hardcodar string na lógica — apenas constroem palavras como sairiam do pdfplumber.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.analysis.commercial import analyze_commercial_region
from core.analysis.confidence import WEIGHTS
from core.analysis.elements import Anchor, BBox
from core.analysis.evidence import Evidence, NEGATIVE, POSITIVE
from core.analysis.reconcile import Candidate, Reconciler
from core.models import ExtractionConfig, PageData
from core.pipeline import EvidenceExtractor

CASA_PDF = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "AVON CASA CICLO 15.pdf"))
REFERENCE_DESC = "Copo com Pingente Patrulha Canina. Plástico. 8,3 cm diâm. X 18,5 cm alt. | 03 pts"

CODES = ["263406", "263656", "263396", "263647", "249833"]


def W(text, x0, x1, top, size=11.0, h=None):
    """Palavra no formato que pdfplumber entrega (dict), usada pelo PageData."""
    h = h if h is not None else (18.0 if size >= 14 else 12.0)
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + h,
            "width": x1 - x0, "height": h, "size": size, "doctop": top}


def _page5_words():
    """Espelho geométrico da página 5 real (CASA): códigos à esquerda, painel
    de regras 1/2/3 POR + descrição compartilhada no centro, promoção à direita
    (9,99 / 60% / LEVE ...) e rodapé para isolar a altura da página."""
    words = []
    # --- coluna de produtos (código + nome/variação abaixo) ---
    for top, code in [(80, "263406"), (110, "263656"), (140, "263396"),
                      (170, "263647"), (200, "249833")]:
        words.append(W(code, 90, 134, top, size=16.0))
    for t in [(96.0, "Marshall", 90, 135), (126.0, "Chase", 92, 130),
              (156.0, "Skye", 92, 124), (186.0, "Skye", 92, 124),
              (216.0, "Chase", 92, 130)]:
        words.append(W(t[1], t[2], t[3], t[0]))
    # --- painel de regras de preço por quantidade (1/2/3 POR) ---
    for qt, pt, q, pr in [(320, 337, "1", "19,99"), (366, 383, "2", "17,99"),
                          (412, 429, "3", "15,99")]:
        words.append(W(q, 250, 258, qt))
        words.append(W("POR", 262, 294, qt))
        words.append(W("R$", 297, 306, qt))
        words.append(W(pr, 298, 354, pt))
        words.append(W("CADA", 358, 392, pt))
    # --- descrição compartilhada do grupo (na banda das regras) ---
    for (text, a, b, y) in [
            ("Copo", 200, 226, 328), ("com", 230, 254, 328),
            ("Pingente", 258, 306, 328), ("Patrulha", 310, 356, 328),
            ("Canina.", 360, 392, 328), ("Plástico.", 200, 240, 344),
            ("8,3", 244, 262, 344), ("cm", 266, 280, 344),
            ("diâm.", 284, 312, 344), ("X", 316, 328, 344),
            ("18,5", 332, 356, 344), ("cm", 360, 374, 344),
            ("alt.", 378, 396, 344), ("|", 200, 208, 356),
            ("03", 212, 228, 356), ("pts", 232, 252, 356)]:
        words.append(W(text, a, b, y))
    # --- promoção separada (bloco à direita) ---
    for (text, a, b, y) in [
            ("60%", 500, 540, 250), ("DE", 544, 562, 250),
            ("DESCONTO", 568, 628, 250),
            ("LEVE", 470, 514, 290), ("1", 518, 530, 290),
            ("CANECA", 534, 588, 290), ("DIVERTIDA", 594, 660, 290),
            ("R$9,99", 610, 664, 290), ("POR", 664, 692, 290),
            ("Na", 470, 492, 390), ("compra", 496, 552, 390),
            ("de", 556, 572, 390), ("2", 576, 584, 390), ("itens", 588, 630, 390)]:
        words.append(W(text, a, b, y))
    # --- rodapé (empurra a altura da página; vira RODAPE, nunca produto) ---
    words.append(W("Rua das Flores", 320, 430, 760))
    return words


def _banner_page_words():
    """Página estilo p65: produtos à esquerda + banner combinatório ÚNICO
    '2 POR R$6,99 ... Combine como quiser.' abaixo (sem sementes de promoção)."""
    words = []
    for top, code in [(250, "263406"), (290, "263656"), (330, "263396")]:
        words.append(W(code, 82, 126, top, size=16.0))
    for t in [(266.0, "Marshall", 82), (306.0, "Chase", 82), (346.0, "Skye", 82)]:
        words.append(W(t[1], t[2], t[2] + 42, t[0]))
    # banner combo abaixo da coluna de produtos
    words.append(W("2", 480, 492, 430))
    words.append(W("POR", 520, 552, 430))
    words.append(W("R$6,99", 556, 610, 430))
    words.append(W("CADA", 614, 648, 430))
    # margem de giro estreita mas LEGÍTIMA (não é a coluna de código): leva
    # o "POR" até as imediações do preço, como nos catálogos reais
    words.append(W("POR", 250, 286, 431))
    words.append(W("Combine", 480, 540, 446))
    words.append(W("como", 544, 572, 446))
    words.append(W("quiser.", 576, 632, 446))
    words.append(W("Guia", 300, 380, 760))
    return words


def _page(words, no):
    return PageData(no, "", [], words)


def _inventory(page):
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    elements, prices, codes, _qty = ex._inventory(page)
    page_h = max((e.bbox.y1 for e in elements), default=0.0)
    return ex, elements, prices, codes, page_h


# --------------------------------------------------------------------------- #
# 1) REGIÃO COMERCIAL — estrutura da página 5 (interpretação do grupo)
# --------------------------------------------------------------------------- #
def test_estrutura_regiao_comercial_pagina5():
    page = _page(_page5_words(), 5)
    ex, elements, prices, codes, page_h = _inventory(page)
    assert len(codes) == 5  # exatamente os 5 códigos da coleção
    assert [c.value for c in sorted(codes, key=lambda c: c.bbox.y0)] == CODES

    region, promo_ids = analyze_commercial_region(5, elements, codes, prices, page_h)

    # variações reconhecidas como nome/variação do código
    assert [u.code for u in region.units] == CODES
    by_code = {u.code: u.variation for u in region.units}
    assert by_code["263406"] == "Marshall"
    assert by_code["263656"] == "Chase"
    assert by_code["263396"] == "Skye"
    assert by_code["263647"] and by_code["263647"].startswith("Skye")
    assert by_code["249833"] and by_code["249833"].startswith("Chase")

    # escada de preço por quantidade (1/2/3 POR) : NÃO é preço três vezes
    assert [r.quantity for r in region.price_rules] == [1, 2, 3]
    assert [r.price for r in region.price_rules] == [19.99, 17.99, 15.99]
    assert sorted(region.tier_rules.items()) == sorted(
        {"19,99": 1, "17,99": 2, "15,99": 3}.items())

    # promoção em bloco separado (benefício + desconto + preço próprio)
    assert region.promo is not None and region.promo.is_oferta
    assert region.promo.price_raw == "9,99"
    assert region.promo.discount == 60
    assert len(promo_ids) >= 1  # preço promocional marcado para exclusão

    # descrição compartilhada: a do painel — sem resto de promoção/regra
    assert region.description == REFERENCE_DESC
    assert "LEVE" not in (region.description or "")
    assert "CANECA" not in (region.description or "")
    assert "9,99" in "".join(region.promo.benefit)


# --------------------------------------------------------------------------- #
# 2) GUARDA ANTI-REGRESSÃO — banner de UMA regra não vira preço de produto
#    (regressão real: p65 '2 POR R$6,99' sequestrou todos os códigos)
# --------------------------------------------------------------------------- #
def test_regra_unica_banner_nao_vira_preco_estrutural():
    page = _page(_banner_page_words(), 65)
    ex, elements, prices, codes, page_h = _inventory(page)

    region, _ = analyze_commercial_region(65, elements, codes, prices, page_h)
    # a regra existe (o banner é real), mas...
    assert [(r.quantity, r.price) for r in region.price_rules] == [(2, 6.99)]

    # ...a guarda exige >=2 regras (escada de tiers) para criar candidato
    st = ex._structure_scan(page, elements, codes, prices, page_h)
    assert st.candidates == {}
    assert st.tiers == {}


def test_regra_unica_banner_fim_a_fim():
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, _stats = ex.run([_page(_banner_page_words(), 65)], include_unpriced=True)
    for it in items:
        assert it.price not in ("6,99", "6,99|", "|6,99")
        assert it.price_extra != "6,99"
        assert "6,99" not in {str(v) for _q, v in (it.quantity_prices or [])}
    assert all(it.price == "" for it in items)  # honesto: NÃO_DETERMINADO


# --------------------------------------------------------------------------- #
# 3) FIM A FIM (sintético) — mesmos comportamentos da página 5 real
# --------------------------------------------------------------------------- #
def test_pagina5_fim_a_fim():
    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, stats = ex.run([_page(_page5_words(), 5)])
    assert stats["grupos_comerciais"] == 1 and stats["promos"] == 1
    assert len(items) == 5

    for it in items:
        assert it.code in CODES
        assert it.price == "19,99"
        assert it.price_extra == "17,99"
        # preço PROMOCIONAL (9,99) nunca é preço de produto
        assert it.price not in ("9,99", "9,99|", "|9,99")
        assert it.price_extra != "9,99"
        assert it.description == REFERENCE_DESC
        assert it.quantity_prices == [[1, "19,99"], [2, "17,99"], [3, "15,99"]]

    by_code = {it.code: it for it in items}
    assert by_code["263406"].variation.startswith("Marshall")
    assert by_code["263656"].variation.startswith("Chase")
    assert by_code["263396"].variation.startswith("Skye")
    assert by_code["263647"].variation.startswith("Skye")
    assert by_code["249833"].variation.startswith("Chase")

    # melhoria "painel no rodapé": o scan column-aligned do painel de preço
    # elevou da FONTE ÚNICA (REVISAR) para MEDIA honesta
    assert all(it.status == "MEDIA" for it in items)
    for it in items:
        assert it.confidence >= 70
        # nota do scanner 'preco_painel' (subset por coluna) + nota N->1 do grupo
        assert "preco_painel" in it.debug
        assert "mesmos precos de" in it.debug


# --------------------------------------------------------------------------- #
# 4) CASO REAL — AVON CASA CICLO 15, página 5
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not os.path.exists(CASA_PDF),
                    reason="PDF real AVON CASA CICLO 15 não está no repositório")
def test_pagina5_real():
    from core.pdf_extractor import PDFDocumentReader

    reader = PDFDocumentReader(CASA_PDF)
    reader.load_document()
    page = next((p for p in reader.pages_data if p.page_number == 5), None)
    assert page is not None, "página 5 não encontrada no AVON CASA CICLO 15"

    ex = EvidenceExtractor(ExtractionConfig(mode="evidence"))
    items, stats = ex.run([page])
    assert stats["codigos"] == 5
    assert stats["associacoes"] == 5
    assert len(items) == 5

    for it in items:
        assert it.code in CODES
        assert it.price == "19,99"
        assert it.price_extra == "17,99"
        assert it.price not in ("9,99", "9,99|", "|9,99")
        assert it.price_extra != "9,99"
        assert it.description == REFERENCE_DESC
        assert it.quantity_prices == [[1, "19,99"], [2, "17,99"], [3, "15,99"]]
        assert "9,99" not in {str(v) for _q, v in (it.quantity_prices or [])}

    by_code = {it.code: it for it in items}
    assert by_code["263406"].variation == "Marshall"
    assert by_code["263656"].variation == "Chase"
    assert by_code["263396"].variation == "Skye"
    assert by_code["263647"].variation == "Skye e Rubble"
    assert by_code["249833"].variation == "Chase e Marshall"

    # painel no rodapé reconhecido por ambos os scans (estrutural + coluna):
    # status honestamente MEDIA, nunca CONFLITO
    assert all(it.status == "MEDIA" for it in items)
    assert all("mesmos precos de" in it.debug for it in items)


# --------------------------------------------------------------------------- #
# 5) RECONCILIAÇÃO — variação do produto NÃO é divergência de descrição
# --------------------------------------------------------------------------- #
def test_reconcile_descricao_ignora_variacao():
    bb = BBox(100, 100, 120, 116)
    price = Anchor("price", "19,99", bb, 5, ["test"], 0.9, {}, [])
    price2 = Anchor("price", "17,99", bb, 5, ["test"], 0.9, {}, [])
    price3 = Anchor("price", "15,99", bb, 5, ["test"], 0.9, {}, [])

    structural = Candidate(
        method="regiao_comercial", code="249833", page=5,
        prices=[price, price2, price3],
        description="Copo com Pingente Patrulha Canina. Plástico. 8,3 cm diâm. X 18,5 cm alt. | 03 pts",
        evidences=[Evidence("preco_valido", "regiao_comercial", 5, POSITIVE, 25.0),
                   Evidence("mesma_regiao", "regiao_comercial", 5, POSITIVE, 20.0)],
        preliminary_score=0.9,
    )
    # scanner geométrico leu a descrição CONTÍGUA (nome + resto do painel)
    regional = Candidate(
        method="regional_cell", code="249833", page=5,
        prices=[price3],
        description=("Chase e Marshall Copo com Pingente Patrulha Canina. "
                     "Plástico. 8,3 cm diâm. X 18,5 cm alt. | 03 pts"),
        evidences=[Evidence("preco_valido", "regional_cell", 5, POSITIVE, 25.0),
                   Evidence("mesma_regiao", "regional_cell", 5, POSITIVE, 20.0),
                   Evidence("distancia_longa", "regional_cell", 5, NEGATIVE, WEIGHTS["distancia_longa"])],
        preliminary_score=0.7,
    )
    rec = Reconciler()
    rel = rec.reconcile("249833", 5, [structural, regional],
                        variation="Chase e Marshall")
    assert rel.description == structural.description
    assert "desc diverge" not in rel.note
    assert {round(p.value, 2) for p in rel.prices} == {19.99, 17.99, 15.99}
    # autoridade estrutural: a penalidade geométrica ('distancia_longa') do
    # scanner periférico NÃO rebaixa o vínculo já confirmado pelo painel
    assert not any(e.claim == "distancia_longa" for e in rel.evidences)

    # sem a variação, a divergência é detectada (diagnóstico preservado),
    # mas como o texto vem de scanner NÃO-estrutural, não penaliza o score
    rel2 = rec.reconcile("249833", 5, [structural, regional], variation="")
    assert "desc diverge" in rel2.note
    desc_evs = [e for e in rel2.evidences
                if e.claim == "descricoes divergem entre metodos"]
    assert desc_evs and desc_evs[0].weight == 0.0