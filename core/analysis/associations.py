# -*- coding: utf-8 -*-
"""
Camada de relacionamento dos dados (ETAPA 4).

Representa as multiplicidades encontradas nos catálogos reais:
    1 código -> 1 preço; 1 código -> N preços (por quantidade / promo);
    N códigos -> 1 preço; N códigos -> N preços.
Não limita a um campo 'preco: float'.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.analysis.elements import Anchor, BBox
from core.analysis.evidence import Evidence


@dataclass
class PriceCondition:
    """Um preço dentro de uma condição comercial específica."""
    value: float
    quantity: Optional[int] = None    # tier de quantidade (ex: 1 un, 2 un)
    unit: Optional[str] = None        # 'un', 'cx', 'ml', 'g', ...
    kind: str = "regular"             # 'regular' | 'promotional' | 'previous' | 'quantity'
    raw: str = ""
    bbox: Optional[BBox] = None
    evidences: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "kind": self.kind,
            "raw": self.raw,
            "bbox": None if not self.bbox else [round(v, 1) for v in
                   (self.bbox.x0, self.bbox.y0, self.bbox.x1, self.bbox.y1)],
            "n_evidencias": len(self.evidences),
        }


@dataclass
class Association:
    """Relacionamento proposto e rastreável entre códigos, descrição e preços."""
    page: int
    codes: List[str]                     # 1..N códigos
    description: Optional[str] = None
    prices: List[PriceCondition] = field(default_factory=list)
    region: Optional[BBox] = None
    evidences: List[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "NAO_DETERMINADO"      # ALTA | MEDIA | REVISAR | CONFLITO | NAO_DETERMINADO
    note: str = ""

    def set_status_by_score(self, score: float) -> None:
        from core.analysis.confidence import classify_score
        self.confidence = score
        if self.status != "CONFLITO":
            self.status = classify_score(score)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "codes": self.codes,
            "description": self.description,
            "prices": [p.to_dict() for p in self.prices],
            "region": None if not self.region else [round(v, 1) for v in
                     (self.region.x0, self.region.y0, self.region.x1, self.region.y1)],
            "confidence": round(self.confidence, 1),
            "status": self.status,
            "note": self.note,
            "evidencias": [e.to_dict() for e in self.evidences],
        }


def parse_value(text: str) -> Optional[float]:
    """Converte texto de valor monetário BR (ex: '8,49', 'R$ 17,99') em float.
    Aceita apenas formatos com casa decimal vírgula e milhar ponto."""
    t = text.strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*[.,]\d*|\d+)", t)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def price_conditions_from_anchors(price_anchors: List[Anchor],
                                  qty_by_value: Optional[Dict[str, int]] = None) -> List[PriceCondition]:
    """Converte âncoras de preço em PriceCondition, aplicando tier de quantidade.
    ``qty_by_value`` mapeia o texto do valor (ex: "8,49") para a quantidade do tier."""
    out: List[PriceCondition] = []
    qty_by_value = qty_by_value or {}
    for a in sorted(price_anchors, key=lambda x: (x.bbox.y0, x.bbox.x0)):
        value = parse_value(a.value)
        if value is None:
            continue
        qty = qty_by_value.get(a.value.strip())
        out.append(PriceCondition(
            value=value,
            quantity=qty,
            kind="quantity" if qty else "regular",
            raw=a.value,
            bbox=a.bbox,
            evidences=[],
        ))
    return out


def cluster_price_conditions(prices: List[PriceCondition],
                             y_tol: float = 45.0, x_tol: float = 60.0) -> List[List[PriceCondition]]:
    """Agrupa preços empilhados (preço normal + preço 2 / anteriores) em blocos."""
    groups: List[List[PriceCondition]] = []
    for p in sorted(prices, key=lambda x: (x.bbox.x0 if x.bbox else 0, x.bbox.y0 if x.bbox else 0)):
        for g in groups:
            last = g[-1]
            if last.bbox and p.bbox:
                if abs(last.bbox.x0 - p.bbox.x0) <= x_tol and 0 <= p.bbox.y0 - last.bbox.y0 <= y_tol:
                    g.append(p)
                    break
            if not last.bbox or not p.bbox:
                g.append(p)
                break
        else:
            groups.append([p])
    return groups