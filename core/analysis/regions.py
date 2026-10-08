# -*- coding: utf-8 -*-
"""
Detecção de regiões / blocos comerciais (ETAPA 4).

A página é dividida em regiões candidatas usando evidências geométricas:
alinhamento de colunas (posição X de códigos), linhas/rects, tabelas e gaps.
Região é uma HIPÓTESE de bloco comercial — não uma verdade absoluta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from core.analysis.elements import Anchor, BBox


@dataclass
class Region:
    """Hipótese de bloco comercial em uma página."""
    page: int
    bbox: BBox
    kind: str = "grid_cell"     # 'grid_cell' | 'table' | 'card' | 'page_band'
    columns: List[Tuple[float, float]] = field(default_factory=list)
    rows_y: Tuple[Optional[float], Optional[float]] = (None, None)
    anchors: List[Anchor] = field(default_factory=list)
    evidence_methods: List[str] = field(default_factory=list)

    def contains(self, anchor: Anchor, x_tol: float = 0.0, y_tol: float = 0.0) -> bool:
        return self.bbox.contains(anchor.bbox, x_tol, y_tol)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "kind": self.kind,
            "bbox": [round(v, 1) for v in (self.bbox.x0, self.bbox.y0,
                                           self.bbox.x1, self.bbox.y1)],
            "columns": [(round(lo, 1), round(hi, 1)) for lo, hi in self.columns],
            "rows_y": [None if r is None else round(r, 1) for r in self.rows_y],
            "anchors": [a.to_dict() for a in self.anchors],
            "evidence": self.evidence_methods,
        }


def detect_gaps(values: Iterable[float], max_gap: float) -> List[Tuple[float, float]]:
    """Converte pontos em grupos fechados por gap: retorna bandas (min, max).
    values ordenáveis; max_gap = distância máxima para pertencer ao mesmo grupo."""
    pts = sorted(set(values))
    if not pts:
        return []
    bands = [[pts[0], pts[0]]]
    for v in pts[1:]:
        if v - bands[-1][1] <= max_gap:
            bands[-1][1] = v
        else:
            bands.append([v, v])
    return [(lo, hi) for lo, hi in bands]


def _column_limits(x_centers: Iterable[float], page_width: float,
                   max_gap: float = 40.0) -> List[Tuple[float, float]]:
    """Bordas de colunas a partir de centros X de códigos; limites interpolados
    entre colunas vizinhas (média), abertas nas extremidades."""
    bands = detect_gaps(x_centers, max_gap)
    if not bands:
        return []
    bounds = []
    for i, (lo, hi) in enumerate(bands):
        left = 0.0 if i == 0 else (bands[i - 1][1] + lo) / 2.0
        right = page_width if i == len(bands) - 1 else (hi + bands[i + 1][0]) / 2.0
        bounds.append((left, right))
    return bounds


def build_grid_regions(page: int, words, code_anchors: List[Anchor],
                       rects=None, tables=None, page_width: float = 1e9,
                       col_gap: float = 40.0, y_band_gap: float = 24.0,
                       max_band_height: float = 420.0) -> List[Region]:
    """Regiões de grade: colunas derivadas dos códigos; células entre faixas
    horizontais de elementos com espaços separadores."""
    radius = 12  # margem em torno das âncoras para delimitar a célula
    cols = _column_limits((a.bbox.cx for a in code_anchors), page_width, col_gap)
    regions: List[Region] = []
    if not cols:
        return regions

    # faixa Y de interesse: entre o topo mais alto e a base mais baixa das âncoras
    if not code_anchors:
        return regions
    y_top = min(a.bbox.y0 for a in code_anchors) - radius
    y_bot = max(a.bbox.y1 for a in code_anchors) + radius

    # subdivisão vertical por faixas de código (agrupadas), cada faixa vira uma linha de região
    code_rows = detect_gaps((a.bbox.cy for a in code_anchors), y_band_gap)
    for (r0, r1) in code_rows:
        for (c0, c1) in cols:
            region_bbox = BBox(max(0, c0 - radius), max(0, r0 - radius),
                               c1 + radius, r1 + max_band_height)
            regions.append(Region(page, region_bbox, kind="grid_cell",
                                  columns=[(c0, c1)], rows_y=(r0, r1)))
    return regions


def build_table_regions(page: int, tables: Optional[Iterable]) -> List[Region]:
    region_regs = []
    if not tables:
        return region_regs
    from core.analysis.elements import (
        PageElement, BBox as _BBox,
    )
    for t in tables:
        # pdfplumber: tabela com bbox ou dataframe
        if isinstance(t, tuple) and len(t) == 4:  # (x0, top, x1, bottom)
            x0, top, x1, bottom = t
            region_regs.append(Region(page, _BBox(x0, top, x1, bottom), kind="table"))
        elif hasattr(t, "bbox"):
            x0, top, x1, bottom = t.bbox
            region_regs.append(Region(page, _BBox(x0, top, x1, bottom), kind="table"))
    return region_regs


def assign_anchors_to_regions(regions: List[Region], anchors: List[Anchor],
                              x_tol: float = 20.0, y_tol: float = 60.0) -> None:
    for a in anchors:
        for r in regions:
            if r.contains(a, x_tol, y_tol):
                r.anchors.append(a)
                break