# -*- coding: utf-8 -*-
"""
Registro de evidências (ETAPA 4).

Toda associação deve registrar COMO foi descoberta. Este módulo define a estrutura
de evidência e o log por página/documento, preservando rastreabilidade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.analysis.elements import BBox

POSITIVE = 1
NEGATIVE = -1
NEUTRAL = 0


@dataclass
class Evidence:
    claim: str                 # legível: "123456 -> R$ 39,90 (celula R3C2)"
    method: str                # 'text_regex' | 'spatial_proximity' | 'region_cell' |
                               # 'table' | 'quantity_ladder' | 'promo_label' | 'reconciliation' ...
    page: int
    polarity: int = POSITIVE
    weight: float = 0.0        # contribuição determinística ao score
    detail: str = ""
    bbox_a: Optional[BBox] = None
    bbox_b: Optional[BBox] = None
    distance_px: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "method": self.method,
            "page": self.page,
            "polarity": self.polarity,
            "weight": round(self.weight, 1),
            "detail": self.detail,
            "dist_px": round(self.distance_px, 1) if self.distance_px is not None else None,
            "a": None if not self.bbox_a else [round(v, 1) for v in
                   (self.bbox_a.x0, self.bbox_a.y0, self.bbox_a.x1, self.bbox_a.y1)],
            "b": None if not self.bbox_b else [round(v, 1) for v in
                   (self.bbox_b.x0, self.bbox_b.y0, self.bbox_b.x1, self.bbox_b.y1)],
        }


@dataclass
class EvidenceLog:
    """Log rastreável de evidências de um documento."""
    entries: List[Evidence] = field(default_factory=list)

    def add(self, claim: str, method: str, page: int, polarity: int = POSITIVE,
            weight: float = 0.0, detail: str = "", bbox_a: Optional[BBox] = None,
            bbox_b: Optional[BBox] = None, distance_px: Optional[float] = None) -> None:
        self.entries.append(Evidence(claim, method, page, polarity, weight,
                                     detail, bbox_a, bbox_b, distance_px))

    def for_page(self, page: int) -> List[Evidence]:
        return [e for e in self.entries if e.page == page]

    def by_method(self, method: str) -> List[Evidence]:
        return [e for e in self.entries if e.method == method]

    def summary(self) -> dict:
        from collections import Counter
        return {
            "total": len(self.entries),
            "positivas": sum(1 for e in self.entries if e.polarity > 0),
            "negativas": sum(1 for e in self.entries if e.polarity < 0),
            "por_metodo": dict(Counter(e.method for e in self.entries)),
        }