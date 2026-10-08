# -*- coding: utf-8 -*-
"""
Modelo espacial de elementos de página (ETAPA 4).

Estruturas puras, sem lógica de negócio: representam a geometria como fonte de
evidência (nunca como verdade absoluta).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class BBox:
    """Caixa limitante normalizada (x0 <= x1, top <= bottom)."""
    x0: float
    y0: float  # ``top``
    x1: float
    y1: float  # ``bottom``

    def __post_init__(self):
        # garante normalização (pdfplumber usa 'top/bottom' e 'y0/y1' invertidos)
        if self.x0 > self.x1 or self.y0 > self.y1:
            x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
            object.__setattr__(self, "x0", min(x0, x1))
            object.__setattr__(self, "x1", max(x0, x1))
            object.__setattr__(self, "y0", min(y0, y1))
            object.__setattr__(self, "y1", max(y0, y1))

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def contains_point(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def overlaps(self, other: "BBox", x_tol: float = 0.0, y_tol: float = 0.0) -> bool:
        return not (self.x1 < other.x0 - x_tol or other.x1 < self.x0 - x_tol
                    or self.y1 < other.y0 - y_tol or other.y1 < self.y0 - y_tol)

    def horizontal_overlap(self, other: "BBox", x_tol: float = 0.0) -> bool:
        return not (self.x1 < other.x0 - x_tol or other.x1 < self.x0 - x_tol)

    def distance_to(self, other: "BBox") -> float:
        dx = max(0.0, max(other.x0 - self.x1, self.x0 - other.x1))
        dy = max(0.0, max(other.y0 - self.y1, self.y0 - other.y1))
        return (dx * dx + dy * dy) ** 0.5

    def centroid_dist_to(self, other: "BBox") -> float:
        return ((self.cx - other.cx) ** 2 + (self.cy - other.cy) ** 2) ** 0.5

    def union(self, other: "BBox") -> "BBox":
        return BBox(min(self.x0, other.x0), min(self.y0, other.y0),
                    max(self.x1, other.x1), max(self.y1, other.y1))

    def contains(self, other: "BBox", x_tol: float = 0.0, y_tol: float = 0.0) -> bool:
        return (self.x0 - x_tol <= other.x0 and self.x1 + x_tol >= other.x1
                and self.y0 - y_tol <= other.y0 and self.y1 + y_tol >= other.y1)


@dataclass
class PageElement:
    """Um elemento bruto preservado do inventário da página."""
    kind: str                      # 'word' | 'char' | 'rect' | 'line' | 'curve' | 'image' | 'table'
    text: str
    bbox: BBox
    size: float = 0.0
    detector: str = ""
    attrs: dict = field(default_factory=dict)

    @property
    def cx(self) -> float:
        return self.bbox.cx

    @property
    def cy(self) -> float:
        return self.bbox.cy

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text,
            "bbox": [round(self.bbox.x0, 1), round(self.bbox.y0, 1),
                     round(self.bbox.x1, 1), round(self.bbox.y1, 1)],
            "size": round(self.size, 2),
            "detector": self.detector,
        }


ANCHOR_KINDS = ("code", "price", "quantity", "unit", "percent", "title",
                "description", "badge", "tone", "unknown")


@dataclass
class Anchor:
    """Uma âncora com origem rastreável (detector) e confiança inicial."""
    kind: str
    value: str
    bbox: BBox
    page: int
    detectors: List[str] = field(default_factory=list)
    confidence: float = 0.0
    meta: dict = field(default_factory=dict)
    elements: List[PageElement] = field(default_factory=list)

    def __post_init__(self):
        if self.kind not in ANCHOR_KINDS:
            self.kind = "unknown"

    def with_kind(self, new_kind: str) -> "Anchor":
        a = Anchor(new_kind, self.value, self.bbox, self.page,
                   list(self.detectors), self.confidence, dict(self.meta), self.elements)
        return a

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "page": self.page,
            "bbox": [round(self.bbox.x0, 1), round(self.bbox.y0, 1),
                     round(self.bbox.x1, 1), round(self.bbox.y1, 1)],
            "detectors": self.detectors,
            "confidence": round(self.confidence, 1),
            "meta": {k: v for k, v in self.meta.items() if not callable(v)},
        }


def merge_anchors(anchors: Sequence[Anchor],
                  x_tol: float = 60.0, y_tol: float = 15.0) -> List[Anchor]:
    """Junta âncoras com mesmo valor e mesma região (ex: preço duplicado pela
    reconstrução 'R$'+número e pelo fallback standalone)."""
    merged: List[Anchor] = []
    for a in sorted(anchors, key=lambda x: (x.value, x.bbox.y0, x.bbox.x0)):
        for m in merged:
            if m.value == a.value and abs(m.bbox.y0 - a.bbox.y0) <= y_tol \
                    and abs(m.bbox.x0 - a.bbox.x0) <= x_tol:
                m.detectors += [d for d in a.detectors if d not in m.detectors]
                m.bbox = m.bbox.union(a.bbox)
                m.elements.extend(a.elements)
                m.confidence = max(m.confidence, a.confidence)
                break
        else:
            merged.append(
                Anchor(a.kind, a.value, a.bbox, a.page, list(a.detectors),
                       a.confidence, dict(a.meta), list(a.elements)))
    return merged


def anchors_within(elements: Iterable[PageElement], bbox: BBox,
                   x_tol: float = 0.0, y_tol: float = 0.0) -> List[PageElement]:
    """Filtra elementos contidos na região (equivalente ao ``crop`` conceitual)."""
    return [e for e in elements if bbox.contains(e.bbox, x_tol, y_tol)]