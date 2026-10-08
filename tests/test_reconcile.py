# -*- coding: utf-8 -*-
"""Testes unitários da reconciliação de scanners (ETAPA 5)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis import Anchor, BBox, Candidate, Reconciler


def anchor(value, x0, y0, x1=None, y1=None):
    return Anchor("price", value, BBox(x0, y0, x1 or x0 + 40, y1 or y0 + 14),
                  1, ["test"])


def cand(method, code, prices, desc=None):
    return Candidate(method, code, 1, prices, description=desc)


def test_sem_candidatos():
    r = Reconciler()
    a = r.reconcile("111", 1, [])
    assert a.status == "NAO_DETERMINADO"


def test_nenhum_candidato_com_preco():
    r = Reconciler()
    a = r.reconcile("111", 1, [cand("coluna", "111", [], desc="Sem preco")])
    assert a.status == "NAO_DETERMINADO"
    assert "nenhum scanner" in a.note


def test_um_scanner_um_preco_media():
    # Cap: fonte única nunca atinge ALTA mesmo com evidência forte.
    r = Reconciler()
    prices = [anchor("49,99", 300, 160)]
    c = cand("regional_cell", "111", prices)
    from core.analysis import Evidence, WEIGHTS
    c.evidences = [Evidence("code_confiavel", "regional_cell", 1, weight=WEIGHTS["code_confiavel"]),
                   Evidence("preco_valido", "regional_cell", 1, weight=WEIGHTS["preco_valido"]),
                   Evidence("mesma_regiao", "regional_cell", 1, weight=WEIGHTS["mesma_regiao"]),
                   Evidence("distancia_muito_curta", "regional_cell", 1, weight=WEIGHTS["distancia_muito_curta"])]
    a = r.reconcile("111", 1, [c])
    # fonte única: mesmo com score alto, cap MEDIA (não confirmada por outro scanner)
    assert a.status == "MEDIA"
    assert [p.value for p in a.prices] == [49.99]


def test_dois_scanners_concordam():
    r = Reconciler()
    same = [anchor("8,49", 100, 400)]
    c1 = cand("regional_cell", "222", same)
    c2 = cand("coluna_banda", "222", same)
    from core.analysis import Evidence, WEIGHTS
    c1.evidences = [Evidence("code_confiavel", "regional_cell", 1, weight=WEIGHTS["code_confiavel"]),
                    Evidence("preco_valido", "regional_cell", 1, weight=WEIGHTS["preco_valido"]),
                    Evidence("mesma_regiao", "regional_cell", 1, weight=WEIGHTS["mesma_regiao"]),
                    Evidence("distancia_curta", "regional_cell", 1, weight=WEIGHTS["distancia_curta"])]
    c2.evidences = [Evidence("alinhamento_coluna", "coluna_banda", 1, weight=WEIGHTS["alinhamento_coluna"])]
    a = r.reconcile("222", 1, [c1, c2])
    assert a.status == "ALTA"  # concordância somou metodos_concordam
    assert any(e.method == "reconciliation" for e in a.evidences)


def test_scanners_divergem_conflito():
    r = Reconciler()
    c1 = cand("regional_cell", "333", [anchor("17,99", 100, 300)])
    c2 = cand("coluna_banda", "333", [anchor("9,90", 100, 305)])
    from core.analysis import Evidence, WEIGHTS
    c1.evidences = [Evidence("mesma_regiao", "regional_cell", 1, weight=WEIGHTS["mesma_regiao"]),
                    Evidence("distancia_muito_curta", "regional_cell", 1, weight=WEIGHTS["distancia_muito_curta"])]
    c2.evidences = [Evidence("alinhamento_coluna", "coluna_banda", 1, weight=WEIGHTS["alinhamento_coluna"]),
                    Evidence("distancia_muito_curta", "coluna_banda", 1, weight=WEIGHTS["distancia_muito_curta"])]
    a = r.reconcile("333", 1, [c1, c2])
    # NUNCA escolhe silenciosamente: mantém os dois preços e status CONFLITO
    assert a.status == "CONFLITO"
    assert sorted(p.value for p in a.prices) == [9.9, 17.99]
    assert any("divergem" in e.claim for e in a.evidences)


def test_um_preco_dois_metodos_diverge_da_tabela_conflito_prevalece():
    # mesmo quando o score somado passaria de ALTA, CONFLITO prevalece
    r = Reconciler()
    c1 = cand("regional_cell", "444", [anchor("6,99", 50, 100)])
    c2 = cand("tabela", "444", [anchor("1,99", 50, 105)])
    from core.analysis import Evidence, WEIGHTS
    c1.evidences = [Evidence("alta", "regional_cell", 1, weight=WEIGHTS["mesma_regiao"]),
                    Evidence("alta2", "regional_cell", 1, weight=WEIGHTS["preco_valido"])]
    c2.evidences = [Evidence("alta3", "tabela", 1, weight=WEIGHTS["preco_valido"]),
                    Evidence("alta4", "tabela", 1, weight=WEIGHTS["mesma_tabela"])]
    a = r.reconcile("444", 1, [c1, c2])
    assert a.status == "CONFLITO"
    assert sorted(p.value for p in a.prices) == [1.99, 6.99]  # os dois valores preservados
    assert a.confidence >= 70  # score alto NÃO esconde o conflito


def test_scanner_incompleto_subset_partial():
    # scanner A viu o preço-2 (stacked), scanner B só o primeiro -> não é conflito
    r = Reconciler()
    c1 = cand("regional_cell", "555", [anchor("22,99", 330, 230), anchor("19,99", 330, 245)])
    c2 = cand("coluna_banda", "555", [anchor("22,99", 330, 230)])
    from core.analysis import Evidence, WEIGHTS
    c1.evidences = [Evidence("a", "regional_cell", 1, weight=WEIGHTS["mesma_regiao"])]
    c2.evidences = [Evidence("b", "coluna_banda", 1, weight=WEIGHTS["alinhamento_coluna"])]
    a = r.reconcile("555", 1, [c1, c2])
    assert a.status != "CONFLITO"
    assert sorted(p.value for p in a.prices) == [19.99, 22.99]  # união preservada


def test_shared_price_groups_n_codigos_1_preco():
    r = Reconciler()
    aa = r.reconcile("1001", 1, [cand("regional_cell", "1001", [anchor("49,99", 300, 500)])])
    bb = r.reconcile("1002", 1, [cand("regional_cell", "1002", [anchor("49,99", 300, 500)])])
    cc = r.reconcile("1003", 1, [cand("regional_cell", "1003", [anchor("9,99", 300, 500)])])
    groups = r.shared_price_groups([aa, bb, cc])
    assert any(set(g) == {"1001", "1002"} for g in groups.values())
    assert all(set(g) != {"1003"} or len(g) > 1 for g in groups.values())


def test_tiers_reconciliados():
    r = Reconciler()
    prices = [anchor("8,49", 377, 588), anchor("6,99", 377, 603)]
    c = cand("regional_cell", "666", prices)
    a = r.reconcile("666", 1, [c], tiers={"8,49": 1, "6,99": 2})
    assert [p.quantity for p in a.prices] == [1, 2]
    assert a.prices[0].kind == "quantity"


def run_tests():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
    print(f"Todos os {len(tests)} testes de reconciliação passaram.")


if __name__ == "__main__":
    run_tests()