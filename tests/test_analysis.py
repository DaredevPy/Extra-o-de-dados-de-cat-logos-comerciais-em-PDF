# -*- coding: utf-8 -*-
"""Testes unitários do modelo de evidências (ETAPA 4)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis import (Anchor, BBox, ConfidenceScorer, PageElement, POSITIVE,
                           WEIGHTS, build_grid_regions, cluster_price_conditions,
                           merge_anchors, price_conditions_from_anchors)


def test_bbox_normaliza_invertidos():
    b = BBox(30, 90, 10, 20)
    assert b.x0 == 10 and b.x1 == 30 and b.y0 == 20 and b.y1 == 90
    assert b.width == 20 and b.height == 70
    assert b.cx == 20 and b.cy == 55
    assert b.contains_point(15, 30)
    assert not b.contains_point(5, 30)


def test_bbox_overlap_e_uniao():
    a = BBox(0, 0, 100, 100)
    b = BBox(80, 80, 200, 200)
    assert a.overlaps(b)
    assert a.distance_to(b) == 0.0
    c = BBox(40, 40, 60, 60)
    assert a.contains(c)
    u = a.union(b)
    assert (u.x0, u.y0, u.x1, u.y1) == (0, 0, 200, 200)


def test_detect_gaps():
    from core.analysis.regions import detect_gaps
    assert detect_gaps([1, 2, 3, 50, 52], 10) == [(1, 3), (50, 52)]
    assert detect_gaps([5, 15, 25], 5) == [(5, 5), (15, 15), (25, 25)]
    assert detect_gaps([], 10) == []


def test_grid_regions_por_coluna_de_codigos():
    codes = [
        Anchor("code", "1000", BBox(60, 100, 90, 112), 1, ["t"]),
        Anchor("code", "1001", BBox(60, 160, 90, 172), 1, ["t"]),
        Anchor("code", "1002", BBox(260, 100, 290, 112), 1, ["t"]),
        Anchor("code", "1003", BBox(260, 190, 290, 202), 1, ["t"]),
    ]
    regs = build_grid_regions(1, [], codes, page_width=400)
    # 2 colunas x 3 linhas de código (cy 106/166/196) = 6 regiões
    assert len(regs) == 6
    cols = {(round(c[0], 1), round(c[1], 1)) for r in regs for c in r.columns}
    assert (0.0, 175.0) in cols and (175.0, 400.0) in cols  # fronteira = ponto médio 90/260


def test_merge_anchors_mesmo_valor():
    a1 = Anchor("price", "39,90", BBox(100, 300, 150, 320), 1, ["r1"], 0.6)
    a2 = Anchor("price", "39,90", BBox(104, 302, 152, 322), 1, ["r2"], 0.4)
    merged = merge_anchors([a1, a2])
    assert len(merged) == 1
    assert set(merged[0].detectors) == {"r1", "r2"}
    assert merged[0].confidence == 0.6


def test_confidence_pesos_centrais():
    s = ConfidenceScorer()
    assert s.weight("mesma_regiao") == 20.0
    assert s.weight("preco_valido") == 25.0
    assert s.weight("distancia_longa") == -15.0
    assert s.weight("regra_inexistente") == 0.0
    # soma com sinal respeitado
    e = [Anchor("price", "x", BBox(0, 0, 1, 1), 1), None, None, None, None, None, None, None, None, None]
    score = s.score(e[0] and [__import__("core.analysis.evidence", fromlist=["Evidence"]).Evidence("a", "m", 1, POSITIVE, s.weight("mesma_regiao"))])
    assert score == 20.0
    assert s.classify(95) == "ALTA"
    assert s.classify(80) == "MEDIA"
    assert s.classify(60) == "REVISAR"


def test_price_conditions_tiers():
    anchors = [
        Anchor("price", "8,49", BBox(0, 100, 60, 115), 1, ["t"]),
        Anchor("price", "6,99", BBox(0, 130, 60, 145), 1, ["t"]),
    ]
    qty_by_value = {"8,49": 1, "6,99": 2}
    conds = price_conditions_from_anchors(anchors, qty_by_value)
    assert [c.value for c in conds] == [8.49, 6.99]
    assert [c.quantity for c in conds] == [1, 2]
    assert all(c.kind == "quantity" for c in conds)
    # cluster: empilhados na mesma coluna em 30px -> 1 bloco
    groups = cluster_price_conditions(conds)
    assert len(groups) == 1 and len(groups[0]) == 2


def test_paginas_sem_associacao_nao_inventam():
    # lista vazia de âncoras -> nenhuma região
    regs = build_grid_regions(1, [], [], page_width=400)
    assert regs == []


def run_tests():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
    print(f"Todos os {len(tests)} testes do modelo de evidências passaram.")


if __name__ == "__main__":
    run_tests()