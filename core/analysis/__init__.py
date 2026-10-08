# -*- coding: utf-8 -*-
"""ETAPA 4 — Modelo de evidências (elementos, regiões, associações, confiança).
Pacote isolado; não altera o parser existente (core/parser.py)."""
from core.analysis.elements import (Anchor, BBox, PageElement, merge_anchors)
from core.analysis.evidence import Evidence, EvidenceLog, NEGATIVE, NEUTRAL, POSITIVE
from core.analysis.confidence import (ConfidenceScorer, WEIGHTS)
from core.analysis.regions import (Region, assign_anchors_to_regions, build_grid_regions)
from core.analysis.associations import (Association, PriceCondition,
                                        cluster_price_conditions,
                                        parse_value,
                                        price_conditions_from_anchors)
from core.analysis.reconcile import Candidate, Reconciler
from core.analysis.commercial import (ClassifiedWord, CommercialRegion,
                                      ProductUnit, PromotionalOffer,
                                      QuantityRule, analyze_commercial_region,
                                      build_text_lines, build_units,
                                      classify_word)

__all__ = [
    "Anchor", "BBox", "PageElement", "merge_anchors",
    "Evidence", "EvidenceLog", "NEGATIVE", "NEUTRAL", "POSITIVE",
    "ConfidenceScorer", "WEIGHTS",
    "Region", "assign_anchors_to_regions", "build_grid_regions",
    "Association", "PriceCondition", "cluster_price_conditions",
    "parse_value", "price_conditions_from_anchors",
    "Candidate", "Reconciler",
    "ClassifiedWord", "CommercialRegion", "ProductUnit", "PromotionalOffer",
    "QuantityRule", "analyze_commercial_region", "build_text_lines",
    "build_units", "classify_word",
]