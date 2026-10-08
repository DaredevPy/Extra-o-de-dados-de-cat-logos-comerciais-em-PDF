# -*- coding: utf-8 -*-
"""
Sistema de confiança determinístico (ETAPA 4).

Pesos CENTRALIZADOS e documentados. Não há IA aqui: a pontuação considera
evidências positivas e negativas e retorna buckets ALTA / MEDIA / REVISAR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from core.analysis.evidence import Evidence

# Pesos centrais (documentação de combinação)
WEIGHTS: dict = {
    # ---- positivas ----
    "code_confiavel": 25.0,          # formato de código válido (6 dígitos / alfanum. c/ dígito)
    "preco_valido": 25.0,            # valor monetário válido reconstruído
    "mesma_regiao": 20.0,            # código e preço no mesmo bloco comercial
    "distancia_muito_curta": 15.0,   # <= 60px entre âncoras
    "distancia_curta": 8.0,          # <= 200px
    "alinhamento_coluna": 10.0,      # mesma faixa X (mesma coluna)
    "mesmo_quadro": 15.0,            # dentro do mesmo rect/caixa visual
    "mesma_tabela": 15.0,            # dentro da mesma tabela detectada
    "tier_identificado": 10.0,       # preço por quantidade identificado
    "metodos_concordam": 15.0,       # dois ou mais scanners concordam
    "dominio_estrutura_grid": 8.0,   # página com grade repetitiva de produtos
    "promocao_identificada": 6.0,    # rótulo promocional (ECONOMIZE, POR, CADA)
    "convencao_formatos": 8.0,       # formato do valor respeita convenção de mercado
    # ---- negativas ----
    "distancia_longa": -15.0,        # > 300px
    "cruza_regiao": -20.0,           # associação cruzando limite de região
    "preco_multi_blocos": -20.0,     # mesmo preço atribuído a blocos incompatíveis
    "metodos_divergem": -15.0,       # scanners divergem (CANDIDATO A CONFLITO)
    "sem_preco_proximo": -10.0,      # sem preço na vizinhança
    "estrutura_ambigua": -10.0,      # geometria ambígua (2 preços equidistantes)
}

# Buckets de status (centralizados)
ALTA_MIN = 90.0
MEDIA_MIN = 70.0


def classify_score(score: float) -> str:
    if score >= ALTA_MIN:
        return "ALTA"
    if score >= MEDIA_MIN:
        return "MEDIA"
    return "REVISAR"


@dataclass
class ConfidenceScorer:
    """Soma determinística de evidências. Toda evidência tem peso da tabela
    central; o score nunca fica abaixo de 0 nem acima de 100."""
    thresholds: tuple = (ALTA_MIN, MEDIA_MIN)

    @classmethod
    def weight(cls, rule: str) -> float:
        return WEIGHTS.get(rule, 0.0)

    def score(self, evidences: Iterable[Evidence],
              cap: float = 100.0, floor: float = 0.0) -> float:
        return min(cap, max(floor, sum(e.weight for e in evidences)))

    def classify(self, score: float) -> str:
        return classify_score(score)

    def score_and_status(self, evidences: List[Evidence]):
        s = self.score(evidences)
        return s, self.classify(s)